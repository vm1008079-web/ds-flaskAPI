import os


def get_credentials():
    """Lee credenciales desde variables de entorno."""
    token = os.getenv('DEEPSEEK_TOKEN')
    cookies = os.getenv('DEEPSEEK_COOKIES')
    if not token or not cookies:
        raise ValueError(
            "Faltan variables de entorno: DEEPSEEK_TOKEN y DEEPSEEK_COOKIES. "
            "Asegúrate de tener un archivo .env o las variables definidas."
        )
    return token, cookies
