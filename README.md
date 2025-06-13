# Translate directory library
A library to manage the translation text writing projects (e.g: LaTeX,
Markdown, Jupyter, MyST, Typst). The library is aimed to simplify and automate
the translation process and compiling of the translated version of the documents.

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

## Documentation

The documentation for the library can be found [here](./docs/main.md)


## Contributing 
The suggestions and pull requests are welcome. Visit the issues pages as well
as the project's [main page](https://github.com/DobbiKov/sci-trans-git) and the
[shared document](https://codimd.math.cnrs.fr/sUW9PQ1tTLWcR98UjLHLpw) in order
to know the current direction and plans of the project.
