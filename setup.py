from setuptools import setup, find_packages
import os

HERE = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(HERE, 'README.rst')).read()
CHANGELOG = open(os.path.join(HERE, 'CHANGELOG.rst')).read()

VERSION = '0.0.1'

setup(name='pyagar',
      version=VERSION,
      description="agar.io python client library",
      long_description=README + '\n\n' + CHANGELOG,
      classifiers=[
          'Programming Language :: Python :: 3.4',
          'Development Status :: 4 - Beta',
          'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)'
      ],
      keywords='agar.io client',
      author='Roberto Abdelkader Martínez Pérez',
      author_email='robertomartinezp@gmail.com',
      url='https://github.com/nilp0inter/pyagar',
      license='LGPLv3',
      packages=find_packages(exclude=["tests", "docs"]),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'PySDL2==0.9.3',
          'requests==2.7.0',
          'websockets==2.4'
      ],
      entry_points={
          'console_scripts':
              ['agar.io=pyagar:main']
      })
