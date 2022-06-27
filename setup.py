from setuptools import setup

setup(
    name='cjdiff',
    version='0.1',
    py_modules=['cjdiff'],
    install_requires=[
        'Click',
        'rich',
        'deepdiff'
    ],
    entry_points='''
        [console_scripts]
        cjdiff=cjdiff:cli
    ''',
)
