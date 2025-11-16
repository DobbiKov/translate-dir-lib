# Translate directory library

A library and a CLI to manage the translation text writing projects (e.g: LaTeX,
Markdown, Jupyter, MyST, Typst). The library is aimed to simplify and automate
the translation process and compiling of the translated version of the documents.

## **Important**

> The library is still in an early phase of development and may have bugs and unimplemented features

## Features

- [x] Project creation
- [x] Source language and the source folder to translate setting
- [x] Target language addition
- [x] Project files syncing (between languages)
- [x] Translation database
- [x] File translation
- [x] Translation correction

The profound explanation of the logic and algorithms of the tool can be found [here](./docs/tool-profound-explanation.md)

## Installation

### For CLI usage
1. Clone the repo: `git clone https://github.com/DobbiKov/translate-dir-lib`
2. Enter to the directory: `cd translate-dir-lib`
3. Install the CLI: `uv tool install -e .`
4. Use it: `translate-dir`
### For in-project library usage

1. Clone the repo: `git clone https://github.com/DobbiKov/translate-dir-lib`
2. Enter to your project where you want to use this library (`cd <your_project_path>`)
3. Install the library as a dependency using `pip`: `pip install <path_to_the_library_directory>`
4. Enjoy!

### For the library development and contribution uses

1. Ensure you have [uv](https://docs.astral.sh/uv/#__tabbed_1_1) tool installed
   (visit their site for the installation guide)
2. Clone the repo: `git clone https://github.com/DobbiKov/translate-dir-lib`
3. Enter `cd translate-dir-lib`
4. Install dependencies `uv sync`
5. Enjoy

## Testing 
1. Install the dependencies using `uv sync`
2. Run tests: `uv run pytest`

## Documentation

The documentation for the library can be found [here](./docs/main.md)

## ToDo

## 📚 Citation

If you use this software in your research or writing, please cite it as follows:

```bib
@software{korotenko-sci-trans-git,
    author = {Yehor Korotenko},
    title = {sci-trans-git},
    year = {2025},
    publisher = {GitHub},
    version = {0.2.0-alpha},
    url = {https://github.com/DobbiKov/sci-trans-git},
    doi = {10.5281/zenodo.15775111}
}
```

## Contributing

The suggestions and pull requests are welcome. Visit the issues pages as well
as the project's [main page](https://github.com/DobbiKov/sci-trans-git) and the
[shared document](https://codimd.math.cnrs.fr/sUW9PQ1tTLWcR98UjLHLpw) in order
to know the current direction and plans of the project.
