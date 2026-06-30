"""
Functions to design the plots
"""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import pandas as pd
import squarify

país = {
    "Argentina":      "Sudamérica",
    "Brasil":         "Sudamérica",
    "Chile":          "Sudamérica",
    "Perú":           "Sudamérica",
    "España":         "Europa",
    "Alemania":       "Europa",
    "Estados Unidos de América": "Norteamérica",
    "Sin Especificar":"Sin dato",
}

#Paleta de colores
blue_dark2 = "#07034A"
blue_dark1 = "#150F8D"
blue_mid  = "#442ED2"
blue_lite = "#4B58A5"
blue_pale = "#84B5DB"
gray     = "#BFBFBF"

dark_blues = {blue_dark2, blue_dark1, blue_mid, blue_lite}

región_palette = {
    "Sudamérica":   [blue_dark1, blue_mid, blue_lite, blue_pale],
    "Europa":       [blue_dark2,  blue_pale],
    "Norteamérica": [blue_lite],
    "Sin dato":     [gray ],
}

def figura_actividad_economica(df: pd.DataFrame, color: str = "#318eba") -> None:

    """
    Economic bar chart by sex

    """
    nombres_cortos = {
        "A: Agricultura, ganadería, silvicultura y pesca": "Agricultura y pesca",
        "B: Explotación de minas y canteras":              "Minería",
        "C: Industrias manufactureras":                    "Manufactura",
        "E: Suministro de agua; evacuación de aguas residuales, gestión de desechos y descontaminación": "Agua y saneamiento",
        "F: Construcción":                                 "Construcción",
        "G: Comercio al por mayor y al por menor, reparación de vehículos automotores y motocicletas": "Comercio y reparaciones",
        "H: Transporte y almacenamiento":                  "Transporte",
        "I: Actividades de alojamiento y de servicio de comidas": "Alojamiento y gastronomía",
        "P: Enseñanza":                                    "Enseñanza",
        "Q: Actividades de atención de la salud humana y de asistencia social": "Salud y asistencia social",
        "S: Otras actividades de servicios":               "Otros servicios",
        "T: Actividades de los hogares como empleadores; actividades no diferenciadas de los hogares como productores de bienes y servicios como uso propio": "Trabajo en hogares",
        "Descripciones incompletas":                       "Descripciones incompletas",
        "Sin especificar":                                 "Sin especificar",
    }

    df = df.copy()
    df["actividad_corta"] = df["actividad_economica"].map(nombres_cortos)
    df["total"] = df["n_mujeres"] + df["n_hombres"]

    otras = df[df["total"] <=4]
    resto = df[df["total"] >  4].copy()
    
    if not otras.empty:
        fila_otras = pd.DataFrame([{
            "actividad_corta": "Otras actividades",
            "n_mujeres": otras["n_mujeres"].sum(),
            "n_hombres": otras["n_hombres"].sum(),
            "total":     otras["total"].sum(),
        }])
        resto = pd.concat([resto, fila_otras], ignore_index=True)

    total_m = resto["n_mujeres"].sum()
    total_h = resto["n_hombres"].sum()
    resto["pct_m"] = resto["n_mujeres"] / total_m * 100
    resto["pct_h"] = resto["n_hombres"] / total_h * 100
    resto = resto.sort_values("pct_h", ascending=True).reset_index(drop=True)


    fig, ax = plt.subplots(figsize=(5, 3))

    y = range(len(resto))
    bar_h = 0.7
    gap = max(8, resto["actividad_corta"].str.len().max() * 0.65)

    ax.barh(y, -resto["pct_m"], left=-gap, height=bar_h,
            color=color, edgecolor="white")
    ax.barh(y,  resto["pct_h"], left= gap, height=bar_h,
            color=color, edgecolor="white")
    
    for yi, cat in zip(y, resto["actividad_corta"]):
        ax.text(0, yi, cat, ha="center", va="center",
                fontsize=6, color="black")

    # Etiquetas de % al final de cada barra
    for yi, pm, ph in zip(y, resto["pct_m"], resto["pct_h"]):
        if pm < 12:
            ax.text(-pm - gap - 0.6, yi, f"{pm:.1f}%",
                    ha="right", va="center", fontsize=8, color="black")
        else:
            ax.text(-pm - gap + 10.4 , yi, f"{pm:.1f}%",
                    ha="right", va="center", fontsize=8, color="white")

        if ph < 12:
            ax.text(ph + gap + 0.6, yi, f"{ph:.1f}%",
                    ha="left", va="center", fontsize=8, color="black")
        else:
            ax.text(ph + gap - 10.4, yi, f"{ph:.1f}%",
                    ha="left", va="center", fontsize=8, color="white")


    max_left  = resto["pct_m"].max()
    max_right = resto["pct_h"].max()
    y_header = len(resto) - 0.2

    ax.text(-gap - max_left/2, y_header, "Mujeres",
            ha="center", va="bottom", fontsize=8, fontweight="bold", color="black")
    ax.text(0, y_header, "Actividad económica",
            ha="center", va="bottom", fontsize=8, fontweight="bold", color="black")
    ax.text( gap + max_right/2, y_header, "Hombres",
            ha="center", va="bottom", fontsize=8, fontweight="bold", color="black")

    ax.set_xlim(-max_left - gap - 10, max_right + gap + 10)
    ax.set_ylim(-0.7, len(resto) + 0.4)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    
    plt.tight_layout()
    plt.show()


def figura_migracion(df: pd.DataFrame) -> None:
    """
    Treemap of migration destinations
    """
    # Agregado por país
    pais = (df.groupby("pais_destino")["n_migrantes"].sum()
              .rename("n").reset_index())
    pais["region"] = pais["pais_destino"].map(país)
    pais["pct"]    = pais["n"] / pais["n"].sum() * 100
    
    region_totals = pais.groupby("region")["n"].sum().sort_values(ascending=False)
    pais["region_total"] = pais["region"].map(region_totals)
    pais = pais.sort_values(["region_total", "n"], ascending=[False, False])

    colors = []
    for region, sub in pais.groupby("region", sort=False):
        palette = región_palette[region]
        for i in range(len(sub)):
            colors.append(palette[min(i, len(palette) - 1)])
    pais["color"] = colors
    
    W, H = 85.0, 60.0
 
    fig, ax = plt.subplots(figsize=(6, 4))

    region_sums  = region_totals
    region_pct   = region_sums / region_sums.sum() * 100

    region_rects = squarify.squarify(
        squarify.normalize_sizes(region_sums.values, W, H),
        x=0, y=0, dx=W, dy=H,
    )
    for rr in region_rects:
        old_y = rr["y"]
        rr["y"] = H - old_y - rr["dy"]

    for region, rr in zip(region_sums.index, region_rects):
        sub = pais[pais["region"] == region].sort_values("n", ascending=False)
        if sub.empty:
            continue

        sub_rects = squarify.squarify(
            squarify.normalize_sizes(sub["n"].values, rr["dx"], rr["dy"]),
            x=rr["x"], y=rr["y"], dx=rr["dx"], dy=rr["dy"],
        )

        for r in sub_rects:
            relative_y = r["y"] - rr["y"]
            r["y"] = (rr["y"] + rr["dy"]) - relative_y - r["dy"]

        for r, (_, row) in zip(sub_rects, sub.iterrows()):
            ax.add_patch(FancyBboxPatch(
                (r["x"], r["y"]), r["dx"], r["dy"],
                boxstyle="round,pad=0,rounding_size=0.8",
                facecolor=row["color"], edgecolor="white", linewidth=2.5,
            ))
            txt_color = "white" if row["color"] in dark_blues else "black"
            area = r["dx"] * r["dy"]

            if   area > 300: fs = 9
            else:           fs = 7

            label_name = "Sin\nEspecificar" if row['pais_destino'] == "Sin Especificar" else row['pais_destino']

            ax.text(
                r["x"] + (r["dx"]*0.05), r["y"] + r["dy"] - (r["dy"]*0.05),
                f"{label_name}\n{row['pct']:.1f}%",
                ha="left", va="top", color=txt_color,
                fontsize=fs, fontweight="medium",
            )
        if region == "Sin dato":
            continue 
        if region == "Norteamérica":
             
             label_y = rr["y"] - 2.5
             va_align = "top"
        else:
            label_y = rr["y"] + rr["dy"] + 1.5
            va_align = "bottom"
        
        ax.text(
            rr["x"] + 0.2, label_y,
            f"{region}  {region_pct[region]:.1f}%",
            color='black',
            fontsize=8, fontweight="medium",
            ha="left", va=va_align,
        )

    ax.set_xlim(-1, 101); ax.set_ylim(-1, 62)
    ax.axis("off")
    ax.set_title("País de destino ",
                 loc="left", fontsize=12,
                 color="black", pad=18)

    plt.tight_layout()
    plt.show()
 
