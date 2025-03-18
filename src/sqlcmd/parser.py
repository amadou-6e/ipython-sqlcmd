import re
from pathlib import Path
import time
from io import StringIO
import pandas as pd
import subprocess
from typing import List, Tuple, Dict, Optional, Any
from IPython import get_ipython

from .exceptions import SQLExecutionError
# from exceptions import SQLExecutionError


def handle_sql_error(
    error_output: str,
    sql_script: str,
    model_name: str = "Unknown",
) -> SQLExecutionError:
    """Factory function to create appropriate SQL error instance"""
    error = SQLExecutionError(error_output, model_name, sql_script)
    print(error)
    raise error


def format_sql_output(stdout: str) -> str:
    """
    Format SQL output dynamically by reading columns as fixed-width with width=1 and eliminating unnecessary columns.

    Args:
        stdout (str): The raw SQL command output (from result.stdout).

    Returns:
        str: Formatted table as a string.
    """
    start_time = time.time()
    if not stdout.splitlines():
        return stdout
    longest_line = max(stdout.splitlines(), key=len)

    df = pd.read_fwf(StringIO(stdout), widths=[1] * len(longest_line), header=None, dtype=str)

    columns_to_remove = []
    for column in df.columns:
        column_data = df[column].fillna(" ").astype(str).str.strip()
        if (column_data == "-").sum() == 1 and (column_data.isin(["", "-"]).all()):
            columns_to_remove.append(column)

    cleaned_df = df.drop(columns=columns_to_remove, errors='ignore')
    cleaned_df = cleaned_df.fillna(" ").astype(str)
    cleaned_output = "\n".join(cleaned_df.apply(lambda row: "".join(row), axis=1))

    print(f"SQL output formatting completed in {time.time() - start_time:.2f} seconds")
    return cleaned_output


def split_sql_batches(sql_content: str) -> List[str]:
    """
    Split SQL content into batches based on GO statements.
    
    Args:
        sql_content: SQL script content
        
    Returns:
        List of SQL batches
    """
    # Use regex to split on GO statements while preserving the original formatting
    batches = re.split(r'\bGO\b', sql_content, flags=re.IGNORECASE)

    # Remove empty batches and trim whitespace
    batches = [batch.strip() for batch in batches if batch.strip()]

    return batches


class SQLParser:
    """Class to handle SQL parsing and transformation."""

    def __init__(self, connection):
        self.connection = connection

    def grant_file_permissions(self, file_path: Path) -> None:
        """
        Grants the SQL database permission to execute the script, in case the user is not logged in
        with the Windows user
        """
        file_path = str(file_path)
        commands = [
            fr'$folder = "{file_path}"', r'$acl = Get-Acl $folder',
            r'$sqlServiceAccount = "NT Service\MSSQLSERVER"',
            r'$accessRule = New-Object System.Security.AccessControl.FileSystemAccessRule($sqlServiceAccount, "Read", "Allow")',
            r'$acl.SetAccessRule($accessRule)', r'Set-Acl $folder $acl'
        ]
        powershell_command = "; ".join(commands)
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", powershell_command],
            capture_output=True,
            text=True)

        if result.returncode != 0:
            print("Error:", result.stderr)

    def resolve_sql_file(self, sql_content: str) -> str:
        """
        Resolves EXECUTE_SQL_FILE commands by replacing them with the actual file contents.
        
        Args:
            sql_content: SQL script content
            
        Returns:
            Resolved SQL script
        """
        pattern = r"EXECUTE_SQL_FILE\s+'([^']+)'|EXECUTE_SQL_FILE\s+\"([^\"]+)\""

        def create_command(file_path: str) -> str:
            resolved_path = file_path
            return (f"PRINT 'executing script at {resolved_path}';"
                    f"EXEC xp_cmdshell '{self.connection.get_sqlcmd_command(resolved_path)}'")

        def wrap_content_for_config(sql_content: str) -> str:
            enable_xp_cmdshell = """
            PRINT '/*'
            EXEC sp_configure 'show advanced options', 1;
            RECONFIGURE;
            EXEC sp_configure 'xp_cmdshell', 1;
            RECONFIGURE;
            PRINT '*/'
            GO
            """

            disable_xp_cmdshell = """
            PRINT '/*'
            EXEC sp_configure 'show advanced options', 1;
            RECONFIGURE;
            EXEC sp_configure 'xp_cmdshell', 0;
            RECONFIGURE;
            PRINT '*/'
            GO
            """

            # Construct the full SQL content
            sql_content = f"""
            {enable_xp_cmdshell}
            {sql_content}
            GO
            {disable_xp_cmdshell}
            """
            return sql_content

        while True:
            match = re.search(pattern, sql_content)
            if not match:
                break

            full_match = match.group(0)
            file_path = match.group(1) or match.group(2)
            file_path = Path(file_path)
            file_path = (Path(Path.cwd(), file_path) if not file_path.is_absolute() else file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"The file {str(file_path)} was not found!")
            self.grant_file_permissions(file_path)
            file_content = create_command(file_path)
            sql_content = sql_content.replace(full_match, file_content)
            sql_content = wrap_content_for_config(sql_content)

        return sql_content

    def substitute_variables(self, query: str) -> str:
        """
        Substitute variables in the query with their values from the IPython namespace.
        
        Args:
            query: SQL query with variables
            
        Returns:
            SQL query with variables substituted
        """
        variable_pattern = re.compile(r"\$(\w+)")

        def replace_variable(match):
            var_name = match.group(1)
            ipy = get_ipython()
            value = ipy.user_ns.get(var_name, None)
            if value is None:
                raise ValueError(f"Variable '{var_name}' is not defined.")
            return str(value)

        return variable_pattern.sub(replace_variable, query)

    def transform_sql(self, sql_content: str) -> str:
        """
        Main transformation function.
        
        Args:
            sql_content: SQL script content
            
        Returns:
            Transformed SQL script
        """
        sql_content = sql_content.replace('%%sqlcmd', '').strip()
        sql_content = self.resolve_sql_file(sql_content)
        return sql_content.replace("GO", "")
