#! /usr/bin/env python
#
try:
    from setuptools import setup, find_packages
except ImportError:
    from distribute_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name = 'stginga',
    version = '0.1.0.dev0',
    provides = ['stginga'],
    packages = find_packages(),
    package_data = {'stginga': ['data/*', 'examples/*/*']},
    scripts = ['scripts/stginga'],
    author = 'STScI',
    author_email = 'help@stsci.edu',
    url = "https://github.com/spacetelescope/stginga",
    description = 'Ginga products specific to STScI data analysis',
    long_description = 'Ginga products specific to STScI data analysis',
    classifiers=[
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering :: Astronomy',
        'Topic :: Software Development :: Libraries :: Python Modules'],
    zip_safe=False,
    use_2to3=True,
    install_requires=['astropy', 'ginga', 'scipy']
)
