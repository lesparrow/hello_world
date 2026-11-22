import openpyxl

SURVEY_CSV = (
    "id;Nom;Email;Sexe;Âge;Note;Tutorat;Satisfaction;Date entretien\n"
    "1;Alami;a.alami@exemple.ma;F;21;12,5;oui;4;15/03/2025\n"
    "2;Bennani;b.bennani@exemple.ma;M;22;9,75;non;2;16/03/2025\n"
    "3;Chraibi;c.chraibi@exemple.ma;F;NSP;14;oui;5;17/03/2025\n"
    "4;Daoudi;d.daoudi@exemple.ma;M;23;;non;3;18/03/2025\n"
    "5;El Idrissi;e.idrissi@exemple.ma;F;20;15,25;oui;4;19/03/2025\n"
    "5;El Idrissi;e.idrissi@exemple.ma;F;20;15,25;oui;4;19/03/2025\n"
    "6;Fassi;f.fassi@exemple.ma;M;24;8;non;1;20/03/2025\n"
    "7;Ghali;g.ghali@exemple.ma;F;22;11;oui;3;21/03/2025\n"
    "8;Hajji;h.hajji@exemple.ma;M;99;10,5;non;2;22/03/2025\n"
    "9;Idrissi;i.idrissi@exemple.ma;F;21;13;oui;5;23/03/2025\n"
    "10;Jabri;j.jabri@exemple.ma;M;22;7,5;non;2;24/03/2025\n"
)


def write_csv(tmp_path, name="enquete.csv", text=SURVEY_CSV, encoding="cp1252"):
    path = tmp_path / name
    path.write_bytes(text.encode(encoding))
    return path


def write_xlsx(tmp_path, name="enquete.xlsx", sheets=None):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    sheets = sheets or {
        "Réponses": [["Groupe", "Score", "Réussite"], ["A", 12.5, True], ["B", 9, False], ["A", 14, True],
                     ["B", None, False], ["A", 11, True]],
        "Notes": [["x"], [1]],
    }
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        for r in rows:
            ws.append(r)
    path = tmp_path / name
    wb.save(path)
    return path
