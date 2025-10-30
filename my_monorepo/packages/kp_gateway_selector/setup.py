from setuptools import setup, find_packages

setup(
    name="kp-gateway-selector",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.0",
        "SQLAlchemy>=1.4",
        "redis>=4.0",
        "cryptography>=3.0",
        "fastapi>=0.111",
        "typing-extensions>=4.7",
        "asgi-correlation-id>=4.0",
        "attrs>=25.4.0,<26.0.0",
    ],
    python_requires=">=3.9,<4.0",
)
