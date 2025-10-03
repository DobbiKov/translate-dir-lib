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
    xml_output, placeholders = latex_to_xml(LATEX_SAMPLE)
    root = ET.fromstring(xml_output)

    text_content = _get_text_content(root)

    assert "Introduction" in text_content
    assert placeholders, "Expected placeholder mapping for LaTeX XML"

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
    xml_output, placeholders = myst_to_xml(MYST_SAMPLE)
    root = ET.fromstring(xml_output)

    text_content = _get_text_content(root)

    assert "Sample MyST Document" in text_content
    assert placeholders, "Expected placeholder mapping for MyST XML"

    reconstructed = reconstruct_from_xml(xml_output)
    assert "print(\"Hello world\")" in reconstructed
