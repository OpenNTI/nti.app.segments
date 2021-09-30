import codecs

from setuptools import find_packages
from setuptools import setup

entry_points = {
    "z3c.autoinclude.plugin": [
        'target = nti.app',
    ],
}

TESTS_REQUIRE = [
    'fudge',
    'nti.app.testing',
    'nti.dataserver[test]',
    'nti.testing',
    'zope.testrunner',
    'nti.app.sites.alpha',
]


def _read(fname):
    with codecs.open(fname, encoding='utf-8') as f:
        return f.read()


setup(
    name='nti.app.segments',
    version=_read('version.txt').strip(),
    author='Bobby Hagen',
    author_email='jason@nextthought.com',
    description="NTI app segments",
    long_description=(
        _read('README.rst') 
        + '\n\n' 
        + _read("CHANGES.rst")
    ),
    license='Apache',
    keywords='pyramid segments',
    classifiers=[
        'Framework :: Zope3',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    url="https://github.com/NextThought/nti.app.segments",
    zip_safe=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    namespace_packages=['nti', 'nti.app'],
    tests_require=TESTS_REQUIRE,
    install_requires=[
        'setuptools',
	'nti.dataserver',
        'nti.externalization',
        'nti.segments',
        'nti.links',
	'nti.metadata',
        'nti.property',
        'nti.schema',
        'requests',
        'pyramid',
        'six',
        'zc.intid',
        'zope.cachedescriptors',
        'zope.component',
        'zope.event',
        'zope.generations',
        'zope.i18nmessageid',
        'zope.intid',
        'zope.interface',
        'zope.location',
        'zope.security',
        'zope.traversing',
    ],
    extras_require={
        'test': TESTS_REQUIRE,
        'docs': [
            'Sphinx',
            'repoze.sphinx.autointerface',
            'sphinx_rtd_theme',
        ],
    },
    entry_points=entry_points,
)
