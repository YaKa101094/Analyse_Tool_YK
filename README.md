# DISCLAIMER
Work in Progress!

Einige Funktionen sind zwar schon implementiert, sind aber noch fehlerhaft.
# Image Browser

Tkinter-basiertes Desktop-Tool zum Laden, Visualisieren und Analysieren von Fluoreszenz-Bilddaten im `.img`-Format (scanbin_s4) sowie gängigen Rasterbildformaten.

---

## Voraussetzungen

- Python ≥ 3.9
- Abhängigkeiten:

```
pip install numpy pillow
```

- Optional: [`photon_tools`](https://github.com/bgamari/photon-tools) für natives `.img`-Laden über `pt.load_image`. Ohne dieses Paket wird ein eigener Fallback-Parser verwendet.

---

## Starten

```bash
python image_browser.py
```

Beim Start sucht das Skript automatisch nach einem Unterordner `img/` im selben Verzeichnis und lädt alle dort gefundenen Bilder.

---

## Unterstützte Dateiformate

| Format | Beschreibung |
|---|---|
| `.img` | scanbin_s4 – proprietäres Format mit zwei Detektorkanälen (detector0, detector1) |
| `.png`, `.jpg`, `.jpeg` | Standardrasterbilder |
| `.tif`, `.tiff` | TIFF |
| `.bmp`, `.webp` | Weitere Rasterformate |

Bei Standard-Rasterbildern wird der Grauwertkanal als `detector0` verwendet; `detector1` bleibt null.

---

## Oberfläche

### Hauptfenster

| Steuerelement | Funktion |
|---|---|
| **◀ Prev / Next ▶** | Blättert durch Einzelbilder (nicht im Grid-Modus relevant) |
| **File** | Dropdown zur direkten Auswahl eines Bildes per Index |
| **Display** | Anzeigemodus (s. unten) |
| **Rows / Cols** | Raster-Dimensionen im Grid-Modus |
| **Threshold** | Relativer Schwellwert (0–1) bezogen auf I_max; beeinflusst Darstellung und Spot-Zählung |
| **Bilder speichern** | Exportiert alle geladenen Bilder als farbkodierte PNGs in `output/` |

### Anzeigemodi

- `grid_sum` – Übersichtsgitter aller Bilder (Summenkanal), mit Spot-Zählung und Intensitätsskala
- `sum` – Einzelansicht Summenkanal
- `detector0` / `detector1` – Einzelansicht je Detektor
- `det0_det1` – Detektoren nebeneinander
- `all` – Alle drei Kanäle nebeneinander

Ein Klick auf ein Bild öffnet eine Vollbild-Detailansicht mit Zoom per Mausrad.

---

## Analyse-Funktionen

### Timetrace

*Menü → Analyse → Timetrace*

Noch nicht implementiert.

### Schichtdicke

*Menü → Analyse → Schichtdicke*

Berechnet für jedes Bild die Schichtdicke aus der Spot-Dichte.

**Threshold-Tabelle:** Zeigt die Spot-Anzahl (oder den Mittelwert über alle Bilder) für Threshold-Werte von 0,00 bis 0,95 in 0,05-Schritten. Exportierbar als `output/threshold_tabelle.csv`.

**Schichtdickenberechnung:**

Eingaben:
- Konzentration *c* [nM]
- Bildfläche *A* [µm²]

Formel:

```
ρ  = c · 10⁻⁹ · N_A / 10¹⁵     [Moleküle/µm³]
d  = N_Spots / (ρ · A) · 1000   [nm]
```

Ausgabe: Schichtdicke pro Bild sowie Mittelwert ± Standardabweichung. Exportierbar als `output/schichtdicke_ergebnisse.csv`.

---

## Spot-Zählung

Ein Pixel gilt als Spot, wenn:

1. er das lokale Maximum in seiner 3×3-Nachbarschaft ist (strikt größer als alle 8 Nachbarn),
2. sein Wert ≥ `threshold × I_max` des jeweiligen Bildes.

---

## Verzeichnisstruktur

```
image_browser.py
img/                  ← Eingabebilder (wird beim Start automatisch gesucht)
output/               ← PNG-Exporte und CSV-Ergebnisse (wird bei Bedarf angelegt)
```

---

## Menü

| Eintrag | Aktion |
|---|---|
| Datei → Pfad öffnen | Öffnet den `img/`-Ordner im Dateiexplorer |
| Datei → Bilder laden | Lädt Bilder neu aus `img/` |
| Datei → Beenden | Schließt die Anwendung |
| Analyse → Timetrace | Öffnet Timetrace-Dialog (Platzhalter) |
| Analyse → Schichtdicke | Öffnet Schichtdicke-Analysefenster |
| Hilfe → Über / Info | Zeigt Versionsinformation |
