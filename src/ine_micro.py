"""
Necessary functions to query the INE 2024 Bolivian Census 

"""

#from __future__ import annotations
import duckdb
import pandas as pd

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Paths to the .json dictionaries generated from the INE variable dictionary
path_root = Path(__file__).parent.parent
dtypes_path = path_root / "censo_2024_data" / "cpv2024_dtypes.json"
labels_path = path_root / "censo_2024_data" / "cpv2024_labels.json"


parquet_files = {
    "persona":   "Persona_CPV-2024.parquet",
    "vivienda":  "Vivienda_CPV-2024.parquet",
    "emigracion": "Emigracion_CPV-2024.parquet",
    "mortalidad": "Mortalidad_CPV-2024.parquet",
}

def load_dtype_dict() -> dict:
    with open(dtypes_path) as f:
        return json.load(f)

def load_labels_dict() -> dict:
    with open(labels_path) as f:
        raw = json.load(f)
    return {var: {int(k): v for k, v in cats.items()}
            for var, cats in raw.items()}


class CensoDB:
    """
    CensoDB wraps DuckDB views over parquet files to efficiently
    query and extract:

    - Population metrics
    - Age-group distribution
    - Local and International migration trends
    - Occupational profiles

    """

    def __init__(self, data_dir: Path | str, *, sep: str = ";"):
        self.data_dir   = Path(data_dir)
        self.sep        = sep
        self.labels     = load_labels_dict()
        self._con       = duckdb.connect()
        self._register_views()

    def _register_views(self):
        for table, filename in parquet_files.items():
            path = self.data_dir / filename
            self._con.execute(f"CREATE VIEW {table} AS SELECT * FROM read_parquet('{path}')")

    def query(self, sql: str) -> pd.DataFrame:
        return self._con.execute(sql).df()

    def label(self, var: str, code: int) -> str:
        """Look up the INE value label for a variable code."""
        return self.labels.get(var, {}).get(code, str(code))
    



    def pueblo_count(self, pueblo_code: int = 1) -> pd.DataFrame:
        """
        Returns population counts of the Bolivians that identify with an specific "pueblo indígena 
        originario campesino o afroboliviano", broken down by department, municipality and sex.

        Queries the census 'persona' table filtering by `P32_PUEBLO_COD` (pueblo_code) and
        `P32_PUEBLO_PER = 1` (self-identified as indigenous), then groups and
        orders results by person count descending.
        """

        df = self.query(f"""
            SELECT
                DEP_RES_COD    AS dep_residencia,
                MUN_RES_COD    AS mun_residencia,
                p25_sexo       AS sexo,
                COUNT(*) AS n_personas
            FROM persona
            WHERE P32_PUEBLO_COD = {pueblo_code}
              AND P32_PUEBLO_PER = 1
            GROUP BY 1,2,3
            ORDER BY n_personas DESC
        """)

        df["dep_residencia"] = df["dep_residencia"].astype(int).map(self.labels.get("DEP_RES_COD", {}))
        df["mun_residencia"] = df["mun_residencia"].astype(int).map(self.labels.get("MUN_RES_COD", {}))
        
        return df
    

    def age_structure(self, pueblo_code: int = 1) -> pd.DataFrame:
        """
        Population filtered by age (in the given ranges: 0-19, 20-39, 40-59, 60+) and sex.
       
        Parameters
        ----------
        pueblo_code : INE pueblo code (78 = Uru del Lago Poopó)

        """
        age_ranges = [(0, 19, "0-19"), (20, 39, "20-39"),
             (40, 59, "40-59"), (60, 200, "60+")]
        
        whens = []
        for lo, hi, lbl in age_ranges:
            if hi >= 200:
                whens.append(f"WHEN P26_EDAD >= {lo} THEN '{lbl}'")
            else:
                whens.append(f"WHEN P26_EDAD BETWEEN {lo} AND {hi} THEN '{lbl}'")
        case = "CASE " + " ".join(whens) + " ELSE 'Sin especificar' END"


        df = self.query(f"""
            SELECT
                {case}    AS grupo_edad,
                P25_SEXO  AS sexo,
                COUNT(*)  AS n_personas
            FROM persona
            WHERE P32_PUEBLO_COD = {pueblo_code}
              AND P32_PUEBLO_PER = 1
            GROUP BY grupo_edad, sexo
            ORDER BY grupo_edad, sexo
        """)

        order = [lbl for _,_, lbl in age_ranges] + ["Sin especificar"]
        df["grupo_edad"] = pd.Categorical(df.grupo_edad, categories=order, ordered=True)

        
        df = (df.assign(sexo=df["sexo"].map(self.labels.get("P25_SEXO", {})))
                    .pivot_table(index="grupo_edad", columns="sexo",
                                 values="n_personas", aggfunc="sum", observed=True)
                    .fillna(0).astype(int).rename_axis(None, axis=1).reset_index())
        return df


    def migration_local_matrix(self, pueblo_code: int = 1, gender: int = 1,
                         dep_filter: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Returns internal migration info for individuals (identified by pueblo_code) who 
        have changed municipalities over the last 5 years (2019 to 2024). You can additionally filter
        by sex and departamento.
        """
        dep_clause = f"AND idep = '{dep_filter:02d}'" if dep_filter else ""

        df =  self.query(f"""
            SELECT
                DEP_RES5_COD   AS dep_origen_2019,
                MUN_RES5_COD   AS mun_origen_2019,
                PROV_RES5_COD  AS prov_origen_2019,
                DEP_RES_COD    AS dep_destino_2024,
                MUN_RES_COD    AS mun_destino_2024,
                PROV_RES_COD   AS prov_destino_2024,         
                COUNT(*)       AS n_personas
            FROM persona
            WHERE P32_PUEBLO_COD = {pueblo_code}
              AND P32_PUEBLO_PER = 1
              AND P37_LUGRES5    = 2    -- was living in a different municipio in 2019
              {dep_clause}
              AND p25_sexo = {gender}
            GROUP BY 1, 2, 3, 4, 5, 6
            ORDER BY n_personas DESC
        """)
        col_map = {
            "dep_origen_2019":   "DEP_RES5_COD",
            "mun_origen_2019":   "MUN_RES5_COD",
            "prov_origen_2019":  "PROV_RES5_COD",
            "dep_destino_2024":  "DEP_RES_COD",
            "prov_destino_2024": "PROV_RES_COD",
            "mun_destino_2024":  "MUN_RES_COD",
        }
        for col, var in col_map.items():
            df[col] = df[col].astype(int).map(self.labels.get(var, {}))

        return df

    def pueblo_occupation(self, pueblo_code: int = 1, gender: int = 1, municipios: list[int] = None) -> dict[str, pd.DataFrame]:
        """
        Economic profile of a pueblo originario.
        Returns a dict of DataFrames, one per thematic block.

        """
        base = f"WHERE P32_PUEBLO_COD = {pueblo_code} AND P32_PUEBLO_PER = 1"

        profile = {}
        codes = ", ".join(str(c) for c in municipios)

        # Occupation 
        profile["ocupacion"] = self.query(f"""
            SELECT
                P49_OCU_1D    AS gran_grupo_ocup,
                P50_SEMP      AS categoria_ocup,
                P51_ACTEC_2D  AS actividad_economica,
                P52_MOV       AS lugar_detrabajo,
                COUNT(*)      AS n
            FROM persona {base} AND p25_sexo = {gender}
            AND MUN_RES_COD in ({codes})
            GROUP BY 1, 2, 3, 4
            ORDER BY n DESC
        """)
        ocu = profile["ocupacion"]
        ocu_map = {
            "gran_grupo_ocup":     "P49_OCU_1D",
            "categoria_ocup":      "P50_SEMP",
            "actividad_economica": "P51_ACTEC_2D",
            "lugar_detrabajo":     "P52_MOV",
        }
        for col, var in ocu_map.items():
            ocu[col] = ocu[col].astype("Int64").map(self.labels.get(var, {}))

        # Without Occupation
        profile["no_ocupados"] = self.query(f"""
            SELECT 
                P48_NOCU AS razon_inactividad,
                COUNT(*) AS n
            FROM persona {base} AND p25_sexo = {gender} 
            AND MUN_RES_COD in ({codes})
            AND P49_OCU_1D IS NULL
            GROUP BY 1 ORDER BY n DESC
        """)
        no_ocu = profile["no_ocupados"]
        no_ocu["razon_inactividad"] = (
            no_ocu["razon_inactividad"].astype("Int64").map(self.labels.get("P48_NOCU", {}))
        )
        return profile

    def international_migration(self, gender: int = 1, pueblo_code: int = 1) -> pd.DataFrame:
        """
        Annual international migration.

        Returns
        -------
        DataFrame: salida_año, pais_destino, edad_salidad, n_migrantes
        """

        df = self.query(f"""
            SELECT
                e.e204_ansal                    AS salida_año,
                e.pais_destino_cod              AS pais_destino,
                CAST(e.e205_edad AS INTEGER)    AS edad_salida,
                COUNT(*)                        AS n_migrantes
            FROM emigracion e
            WHERE e.e203_sexo = {gender}
            AND EXISTS (
                SELECT 1 FROM persona p
                WHERE p.idep = e.idep  AND p.iprov = e.iprov
                AND p.imun = e.imun  AND p.i00 = e.i00
                AND P32_PUEBLO_COD = {pueblo_code}
                AND P32_PUEBLO_PER = 1
            )
            GROUP BY 1, 2, 3
            ORDER BY salida_año, n_migrantes DESC
        """)    
        df["pais_destino"] = df["pais_destino"].astype(int).map(self.labels.get("PAIS_DESTINO_COD", {}))
        
        return df
