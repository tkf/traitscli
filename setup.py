from distutils.core import setup

import traitscli

setup(
    name='traitscli',
    version=traitscli.__version__,
    py_modules=['traitscli'],
    author=traitscli.__author__,
    author_email='aka.tkf@gmail.com',
    url='https://github.com/tkf/traitscli',
    license=traitscli.__license__,
    description='traitscli - CLI generator based on class traits',
    long_description=traitscli.__doc__,
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
