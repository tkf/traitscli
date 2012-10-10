all: traitscli.py README.rst

README.rst: _cogutils.py
	cog.py -r $@ traitscli.py
	cog.py -r $@

traitscli.py: _cogutils.py README.rst
	cog.py -r $@ README.rst
	cog.py -r $@

doc: traitscli.py
	make -C doc html

upload: traitscli.py
	python setup.py register sdist upload
