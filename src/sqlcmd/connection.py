import urllib.parse
from typing import Dict, Optional


class SQLConnection:
    """Class to manage SQL Server connection information."""

    def __init__(self):
        self.connection_string: Optional[str] = None
        self.connection_info: Optional[Dict[str, str]] = None
        self.encoding: str = "65001"

    def set_encoding(self, sqlcmd_encoding):
        self.encoding = sqlcmd_encoding

    def set_connection_string(self, connection_string: str) -> bool:
        """
        Set and parse the connection string.
        
        Args:
            connection_string: MSSQL connection string in the format mssql+sqlcmd:///?odbc_connect=...
            
        Returns:
            bool: True if connection string was successfully parsed, False otherwise
        """
        self.connection_string = connection_string.strip("'")

        try:
            if "mssql+sqlcmd:///?odbc_connect=" in self.connection_string:
                odbc_connect_part = urllib.parse.unquote(
                    self.connection_string.split("odbc_connect=")[1])
                params = dict(
                    item.split("=") for item in odbc_connect_part.split(";") if "=" in item)

                # Extract server, database, username, password from the connection parameters
                self.connection_info = {
                    "server": params.get("SERVER", "localhost"),
                    "database": params.get("DATABASE", "master"),
                    "username": params.get("UID", ""),
                    "password": params.get("PWD", ""),
                }
                return True
            else:
                return False
        except Exception:
            self.connection_string = None
            self.connection_info = None
            return False

    def get_sqlcmd_command(self, file_path: str) -> str:
        """
        Generate the sqlcmd command line for executing a SQL file.
        
        Args:
            file_path: Path to the SQL file to execute
            
        Returns:
            str: The sqlcmd command line
        """
        if not self.connection_info:
            raise ValueError("No connection information available")

        server = self.connection_info["server"]
        database = self.connection_info["database"]
        username = self.connection_info["username"]
        password = self.connection_info["password"]
        file_path = f'"{str(file_path)}"'
        return f"sqlcmd -s\"|\" -S {server} -d {database} -U {username} -P {password} -b -i {file_path} -f {self.encoding} -r 1 -W"
