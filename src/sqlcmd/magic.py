import os
import urllib.parse
from IPython.core.magic import Magics, magics_class, line_cell_magic
from IPython.core.magic_arguments import magic_arguments, argument, parse_argstring
from IPython import get_ipython

from .connection import SQLConnection
from .parser import SQLParser
from .executor import SQLExecutor

ENCODING_MAP = {
    "utf-8": "65001",
    "latin-1": "1252",
    "cp1252": "1252",
    "cp850": "850",
    "cp437": "437",
    "cp1251": "1251",
    "cp1250": "1250",
    "shift_jis": "932",
    "big5": "950",
    "gb2312": "936",
    "euc-kr": "949",
    "utf-16": "1200"
}


@magics_class
class SQLCmdMagic(Magics):
    """IPython magic for SQLCMD execution."""

    def __init__(self, shell):
        super().__init__(shell)
        self.connection = SQLConnection()
        self.parser = SQLParser(self.connection)
        self.executor = SQLExecutor(self.connection, self.parser)

    def _build_connection_string(self, server, database, username, password, driver, encrypt,
                                 trust_cert):
        """
        Build a connection string from individual parameters.
        
        Args:
            server (str): The SQL Server instance
            database (str): The database name
            username (str): SQL Server username
            password (str): SQL Server password
            driver (str): ODBC driver name
            encrypt (bool): Whether to encrypt the connection
            trust_cert (bool): Whether to trust the server certificate
            
        Returns:
            str: A connection string in the format expected by SQLConnection
        """
        # Build the ODBC connection string
        odbc_string = (f"DRIVER={{{driver}}};"
                       f"SERVER={server};"
                       f"DATABASE={database};"
                       f"UID={username};"
                       f"PWD={password};")

        # Add encryption options if specified
        if encrypt:
            odbc_string += "Encrypt=yes;"
        if trust_cert:
            odbc_string += "TrustServerCertificate=yes;"

        # URL encode the ODBC string
        encoded_conn = urllib.parse.quote_plus(odbc_string)

        # Return the full sqlcmd magic connection string
        return f"mssql+sqlcmd:///?odbc_connect={encoded_conn}"

    @line_cell_magic
    @magic_arguments()
    @argument('connection', nargs='?', help='Connection string or database name')
    @argument('--server',
              '-s',
              default='localhost',
              help='SQL Server instance (default: localhost)')
    @argument('--username', '-u', default='sa', help='SQL Server username (default: sa)')
    @argument('--password', '-p', help='SQL Server password')
    @argument('--password-env',
              '-e',
              default='SSMS_PASSWORD',
              help='Environment variable containing password (default: SSMS_PASSWORD)')
    @argument('--encoding',
              '-c',
              help='Output and SQL database encoding',
              default='utf-8',
              choices=ENCODING_MAP.keys())
    @argument('--driver',
              '-d',
              default='ODBC Driver 17 for SQL Server',
              help='ODBC driver name (default: ODBC Driver 17 for SQL Server)')
    @argument('--show-execution-time',
              '-t',
              action='store_true',
              default=False,
              help='Show execution times of queries')
    @argument('--encrypt',
              action='store_true',
              default=True,
              help='Encrypt connection (default: True)')
    @argument('--no-encrypt',
              dest='encrypt',
              action='store_false',
              help='Do not encrypt connection')
    @argument('--trust-certificate',
              action='store_true',
              default=True,
              help='Trust server certificate (default: True)')
    @argument('--no-trust-certificate',
              dest='trust_certificate',
              action='store_false',
              help='Do not trust server certificate')
    @argument('--debug', action='store_true', help='Enable debug mode to print verbose output')
    def sqlcmd(self, line, cell=None):
        """
        Magic that works as both line and cell magic.
        
        Usage as line magic with connection string:
            %sqlcmd 'mssql+sqlcmd:///?odbc_connect=...'
            
        Usage as line magic with parameters:
            %sqlcmd AdventureWorks --server=myserver --username=myuser --password=mypassword
            
        Usage with password from environment variable:
            %sqlcmd AdventureWorks --password-env=MY_SQL_PASSWORD
            
        Usage as cell magic:
            %%sqlcmd [--debug]
            SQL code here
        """
        args = parse_argstring(self.sqlcmd, line) if line else None
        debug = getattr(args, "debug", False) if args else False
        encoding = getattr(args, "encoding", False) if args else "utf-8"
        show_execution_time = getattr(args, "show_execution_time", False) if args else False

        if cell is None:
            # Line magic mode - set connection string or parameters
            if not args or not args.connection:
                print("Error: Database name or connection string is required.")
                return

            connection_str = args.connection

            # Check if this is a full connection string or just a database name
            if 'odbc_connect=' not in connection_str and '://' not in connection_str:
                # This is just a database name, so build the connection string
                password = args.password
                if password is None:
                    # Try to get password from environment variable
                    password = os.getenv(args.password_env)
                    if password is None:
                        print(
                            f"Error: Password not provided and environment variable {args.password_env} not set."
                        )
                        return

                connection_str = self._build_connection_string(
                    server=args.server,
                    database=connection_str,  # First positional arg is the database
                    username=args.username,
                    password=password,
                    driver=args.driver,
                    encrypt=args.encrypt,
                    trust_cert=args.trust_certificate)

            success = self.connection.set_connection_string(connection_str)
            self.connection.set_encoding(ENCODING_MAP.get(encoding))
            if success:
                # Mask the password before printing
                masked_connection_info = self.connection.connection_info.copy()
                if "password" in masked_connection_info and masked_connection_info["password"]:
                    masked_connection_info["password"] = "***"

                masked_connection_string = self.connection.connection_string.replace(
                    f"PWD={self.connection.connection_info['password']}",
                    "PWD=***") if self.connection.connection_info[
                        "password"] else self.connection.connection_string

                # Print masked connection details
                print(f"Connection string set: {masked_connection_string}")
                print(f"Parsed connection info: {masked_connection_info}")
            else:
                print("Error: Invalid connection string format.")
        else:
            # Cell magic mode - execute SQL
            if not self.connection.connection_info:
                print("Error: No connection information provided. Use "
                      "%sqlcmd to set the connection string.")
                return

            self.executor.execute_sql(cell,
                                      debug=debug,
                                      encoding=encoding,
                                      print_timing=show_execution_time)


def load_ipython_extension(ipython):
    """
    Load the extension in IPython.
    """
    ipython.register_magics(SQLCmdMagic)
