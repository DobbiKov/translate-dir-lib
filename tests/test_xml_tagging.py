import xml.etree.ElementTree as ET

from trans_lib.enums import ChunkType
from trans_lib.xml_manipulator_mod.mod import chunk_to_xml, latex_to_xml, myst_to_xml
from trans_lib.xml_manipulator_mod.xml import reconstruct_from_xml


LATEX_SAMPLE = r"""\section*{Introduction}
Here is an inline equation $E=mc^2$ and a labeled reference \ref{eq:energy}.

\begin{align}
  a &= b + c \\
  d &= e + f \text{Hello there}
\end{align}

We also include a verbatim example: \verb|printf(\"hi\")|.

\begin{equation}\label{eq:energy}
  \int_0^\infty e^{-x} dx = 1
\end{equation}
"""


MYST_SAMPLE = """
# Sample MyST Document

:::{admonition} Note
Stay hydrated.
:::

```{code-cell} python3
print(\"Hello world\")
```

Some inline math: $E = mc^2$.

```{math}
a^2 + b^2 = c^2
```

A definition using MyST roles: {term}`energy`.


Wait:
- [Jupyter: mode édition versus mode commande <status>](jupyter/mode-edition-vs-commande.md)
- [Valeurs et types <status>](premiers-calculs/01-valeurs-types.md)
- [Fonctions mathématiques <status>](premiers-calculs/02-fonctions-maths.md)
- [Variables <status>](premiers-calculs/03-variables.md)
- [Premières fonctions <status>](fonctions/00-initiation-fonctions.md)
"""


def _get_text_content(root: ET.Element) -> str:
    """Return the concatenated textual content of the XML tree."""
    return "".join(root.itertext())


def test_latex_chunk_to_xml_produces_valid_xml():
    xml_output = chunk_to_xml(LATEX_SAMPLE, ChunkType.LaTeX)
    print(xml_output)
    root = ET.fromstring(xml_output)

    assert root.tag == "document"
    assert root.findall(".//PH"), "Expected placeholder tags in LaTeX XML output"

    reconstructed = reconstruct_from_xml(xml_output)
    print("====][]")
    print(reconstructed)
    assert "Introduction" in reconstructed


def test_latex_to_xml_preserves_text_segments_and_placeholders():
    xml_output, placeholders, ph_only = latex_to_xml(LATEX_SAMPLE)
    root = ET.fromstring(xml_output)

    text_content = _get_text_content(root)

    assert "Introduction" in text_content
    assert placeholders, "Expected placeholder mapping for LaTeX XML"
    assert ph_only is False

    reconstructed = reconstruct_from_xml(xml_output)
    assert "\\begin{align}" in reconstructed


def test_myst_chunk_to_xml_produces_valid_xml():
    xml_output = chunk_to_xml(MYST_SAMPLE, ChunkType.Myst)
    print("---myst")
    print(xml_output)
    root = ET.fromstring(xml_output)

    assert root.tag == "document"
    assert root.findall(".//PH"), "Expected placeholder tags in MyST XML output"

    reconstructed = reconstruct_from_xml(xml_output)
    print("===[]")
    print(reconstructed)
    assert "Stay hydrated." in reconstructed


def test_myst_to_xml_preserves_text_segments_and_placeholders():
    xml_output, placeholders, ph_only = myst_to_xml(MYST_SAMPLE)
    root = ET.fromstring(xml_output)

    text_content = _get_text_content(root)

    assert "Sample MyST Document" in text_content
    assert placeholders, "Expected placeholder mapping for MyST XML"
    assert ph_only is False

    reconstructed = reconstruct_from_xml(xml_output)
    assert "print(\"Hello world\")" in reconstructed


def test_myst_list_item_preserves_continuation_lines():
    source = "- hey\n  hey\n  hey\n"
    xml_output, _, _ = myst_to_xml(source)
    reconstructed = reconstruct_from_xml(xml_output)

    assert "- hey\n  hey\n  hey" in reconstructed
    assert reconstructed.count("\n  hey") == 2


def test_myst_inline_link_round_trip_preserves_markup():
    source = "Paragraph with [example](https://example.com) link.\n\nSecond paragraph.\n"
    xml_output, _, _ = myst_to_xml(source)
    reconstructed = reconstruct_from_xml(xml_output).rstrip()

    lines = reconstructed.splitlines()

    assert lines[0] == "Paragraph with [example](https://example.com) link."
    assert lines[1] == ""
    assert lines[2] == "Second paragraph."


def test_myst_admonition_with_list_round_trip():
    source = ":::{admonition} Tip\n- item\n  detail\n:::\n"
    xml_output, _, _ = myst_to_xml(source)
    reconstructed = reconstruct_from_xml(xml_output).rstrip()

    lines = reconstructed.splitlines()

    assert lines[0] == ":::{admonition} Tip"
    assert "- item" in lines[1]
    assert lines[2] == "  detail"
    assert lines[-1] == ":::"


def test_myst_nested_lists_preserve_indentation():
    source = "- outer\n  1. inner\n     - detail\n       line\n"
    xml_output, _, _ = myst_to_xml(source)
    reconstructed = reconstruct_from_xml(xml_output).rstrip()

    lines = reconstructed.splitlines()

    assert lines[0] == "- outer"
    assert lines[1] == "\t1. inner"
    assert lines[2] == "\t\t- detail"
    assert lines[3] == "\t\t  line"


def test_myst_course_outline_round_trip_preserves_structure():
    source = """1. Chaque feuille ci-dessous correspond à un défi. Ouvrez-les tour à tour dans l'ordre et\n   suivez les instructions incluses. Vous pouvez cocher les cases ci-dessous au fur et à\n   mesure que vous finissez les feuilles. Si vous bloquez sur l'un des défis, n'hésitez\n   pas à passer à la suite et y revenir ultérieurement.\n\n   % Déposez votre travail après chaque fiche.\n\n   - [Prise en main de Laby <status>](premiers-pas/01-prise-en-main-laby.md)\n   - [À vous de jouer <status>](premiers-pas/10-premier-exo.md)\n   - [Un caillou dans la chaussure <status>](premiers-pas/11-un-caillou.md)\n   - [Encore un caillou! <status>](premiers-pas/12-encore-un-caillou.md)\n   - [Le débogueur <status>](premiers-pas/13-pas-%C3%A0-pas.md)\n\n   Répéter :\n\n   % boucles while\n\n   - [Que c'est loin! <status>](premiers-pas/20-on-regarde-devant-soi.md)\n   - [Le couloir des cailloux <status>](premiers-pas/21-beaucoup-de-cailloux.md)\n\n   % et petites fonctions\n\n   - [En zigzag <status>](premiers-pas/22-en-zigzag.md)\n   - [La spirale infernale <status>](premiers-pas/23-la-spirale.md)\n\n   %- ♣ [Encore un zigzag <status>](premiers-pas/24-encore-un-zigzag.md)\n\n   S'adapter :\n\n   % conditionnelles\n\n   - [Ahhh des toiles! <status>](premiers-pas/30-si-si-si.md)\n\n   %- [Le caillou et la toile <status>](premiers-pas/31-le-caillou-et-la-toile.md)\n\n   Compter :\n\n   % boucles for et variables\n\n   - [Tu répéteras trois fois <status>](boucles/02-boucles-for-introduction-laby.md)\n   - [Variables <status>](premiers-pas/41-variables.md)\n   - [Compter les cailloux <status>](premiers-pas/42-compter.md)\n"""
    xml_output, _, _ = myst_to_xml(source)
    reconstructed = reconstruct_from_xml(xml_output).rstrip()
    normalized = (reconstructed
                  .replace('\u00a0', ' ')
                  .replace('’', "'")
                  )

    lines = normalized.splitlines()

    assert lines[0].startswith("1. Chaque feuille ci-dessous correspond à un défi")
    assert "Déposez votre travail" in lines[3]

    bullet_lines = [line for line in lines if line.startswith("\t- [")]
    assert len(bullet_lines) == 13, "Expected all nested bullet links to survive"

    assert "%  boucles while" in normalized
    assert "%  boucles for et variables" in normalized
    assert "% - ♣ [Encore un zigzag <status>](premiers-pas/24-encore-un-zigzag.md)" in normalized
    assert "% - [Le caillou et la toile <status>](premiers-pas/31-le-caillou-et-la-toile.md)" in normalized
    assert "S'adapter :" in normalized
    assert "Compter :" in normalized


def test_myst_numbered_item_with_continuation_lines():
    source = "2. just test\n  haha\n"
    xml_output, _, _ = myst_to_xml(source)
    reconstructed = reconstruct_from_xml(xml_output).rstrip()

    assert reconstructed.splitlines() == ["2. just test", "   haha"]
