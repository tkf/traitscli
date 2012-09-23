from distutils.core import setup


def parse_traitscli():
    """Evaluate lines in traitscli.py just before imports."""
    import itertools
    with open('traitscli.py') as f:
        lines = itertools.takewhile(lambda x: not x.startswith('__all__ ='),
                                    iter(f.readline, ''))
        src = ''.join(lines)
    data = {}
    exec src in data
    return data


data = parse_traitscli()

setup(
    name='traitscli',
    version=data['__version__'],
    py_modules=['traitscli'],
    author=data['__author__'],
    author_email='aka.tkf@gmail.com',
    url='https://github.com/tkf/traitscli',
    license=data['__license__'],
    description='traitscli - CLI generator based on class traits',
    long_description=data['__doc__'],
    keywords='CLI, traits',
    classifiers=[
        "Development Status :: 3 - Alpha",
        # see: http://pypi.python.org/pypi?%3Aaction=list_classifiers
    ],
    install_requires=[
        'argparse',
        'traits',
    ]
)
