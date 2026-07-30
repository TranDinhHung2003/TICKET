from setuptools import setup, find_packages

setup(
    name="fb-group-poster",
    version="1.0.0",
    description="Tool đăng bài quảng cáo lên các nhóm Facebook",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "click>=8.1.7",
        "rich>=13.7.0",
        "tenacity>=8.2.3",
    ],
    entry_points={
        "console_scripts": [
            "fb-poster=fb_poster.cli:main",
        ],
    },
)
