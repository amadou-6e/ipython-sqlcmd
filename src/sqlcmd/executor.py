import subprocess
import time
import re
import pandas as pd
from pathlib import Path
from typing import Optional, Tuple
from .parser import split_sql_batches
# from parser import split_sql_batches

# Global directory for caching session output
CACHE_DIR = Path(Path.home(), "sqlcmd_magic_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def parse_output_to_dataframe(output: str) -> Tuple[Optional[pd.DataFrame], str]:
    """Parse piped SQL output into a DataFrame and return metadata."""
    if not output or '|' not in output:
        return None, output

    # Split into lines and filter out any blank lines
    lines = [line for line in output.strip().split('\n') if line.strip()]
    if len(lines) < 3:  # Need at least header, separator, and one data row
        return None, output

    # Find where data ends - first line containing "rows affected"
    data_end = next((i for i, line in enumerate(lines) if "rows affected" in line), len(lines))
    if data_end <= 2:
        return None, output

    # Header is the first line; strip each column name
    column_names = [col.strip() for col in lines[0].split('|')]

    # Data starts at line 2 (after header and separator)
    data_rows = []
    for i in range(2, data_end):
        row_values = [value.strip() for value in lines[i].split('|')]
        if len(row_values) < len(column_names):
            row_values.extend(['NULL'] * (len(column_names) - len(row_values)))
        data_rows.append(row_values)

    # Create DataFrame and replace "NULL" with None
    df = pd.DataFrame(data_rows, columns=column_names)
    df = df.replace("NULL", None)

    # Metadata is everything after the table data
    metadata = "\n".join(lines[data_end:])
    return df, metadata


class SQLExecutor:
    """Class to handle SQL execution."""

    def __init__(self, connection, parser):
        self.connection = connection
        self.parser = parser
        self.last_output = ""  # Store the last command output

    def parse_output_to_dataframe(self, output: str) -> Tuple[Optional[pd.DataFrame], str]:
        """
        Parse piped SQL output into a DataFrame and return metadata.
        
        Args:
            output: The raw SQL output with pipe delimiters
            
        Returns:
            Tuple containing (DataFrame or None, metadata string)
        """
        if not output or '|' not in output:
            return None, output

        # Split into lines and filter out any blank lines
        lines = [line for line in output.strip().split('\n') if line.strip()]

        if len(lines) < 3:  # Need at least header, separator, and one data row
            return None, output

        # Find where data ends - first line containing "rows affected"
        data_end = next((i for i, line in enumerate(lines) if "rows affected" in line), len(lines))

        # If no actual data rows (just header and separator), return None
        if data_end <= 2:
            return None, output

        # Header is the first line
        column_names = lines[0].split('|')

        # Data starts at line 2 (after header and separator), goes until data_end
        data_rows = []
        for i in range(2, data_end):
            row_values = lines[i].split('|')
            # Ensure consistent column count
            if len(row_values) < len(column_names):
                row_values.extend(['NULL'] * (len(column_names) - len(row_values)))
            data_rows.append(row_values)

        # Create DataFrame
        df = pd.DataFrame(data_rows, columns=column_names)

        # Metadata is everything after the data
        metadata = '\n'.join(lines[data_end:])

        # Replace "NULL" with None
        df = df.replace("NULL", None)

        return df, metadata

    def execute_sql(self,
                    sql_content: str,
                    encoding: str = "utf-8",
                    debug: bool = False,
                    print_timing: bool = False) -> Optional[pd.DataFrame]:
        """
        Execute SQL content and optionally return results as DataFrame.
        
        Args:
            sql_content: SQL script content
            debug: Whether to enable debug mode
        """
        start_time = time.time()
        modified_content = self.parser.substitute_variables(sql_content)
        modified_content = self.parser.transform_sql(modified_content)

        # Split the SQL content into batches based on GO statements
        batches = split_sql_batches(modified_content)

        # Create a temporary directory for batch files
        temp_dir = CACHE_DIR / f"sql_batches_{int(time.time())}"
        temp_dir.mkdir(exist_ok=True)

        total_exec_duration = 0
        self.last_output = ""  # Reset the last output
        self.last_dataframe = None  # Reset last DataFrame result
        last_df = None

        try:
            for i, batch in enumerate(batches):
                if not batch.strip():  # Skip empty batches
                    continue

                batch_file = temp_dir / f"batch_{i}.sql"
                with open(batch_file, 'w') as f:
                    f.write(batch)

                if debug:
                    print(f"\nExecuting query {i+1}/{len(batches)}:")
                    print(f"Query file: {batch_file}")
                    print("SQL content:")
                    formatted_sql = "\n".join(f" |{line}" for line in batch.splitlines())
                    print(formatted_sql)

                exec_start_time = time.time()
                command = self.connection.get_sqlcmd_command(batch_file)

                if debug:
                    print("Command:", command)

                # This list will accumulate all DataFrames detected in the stream
                dataframe_list = []

                stdout_print_flag = True
                error_print_flag = True

                with subprocess.Popen(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding=encoding,  # add encoding option
                ) as proc:

                    # Process stdout and stderr live
                    table_data_lines = []
                    collecting_table = False
                    separator_seen = False

                    for line in proc.stdout:
                        out = line.strip()

                        # If the line appears to be part of a table (contains a pipe)
                        if '|' in out:
                            collecting_table = True
                            table_data_lines.append(out)
                            # Check if this is the separator line (only dashes, pipes, or spaces)
                            if not separator_seen and re.match(r'^[-\| ]+$', out.replace(' ', '')):
                                separator_seen = True
                            continue
                        elif collecting_table and separator_seen:
                            # If we are in a table block and get a line that is either empty or starts with '(',
                            # we treat it as the end of the table block.
                            if not out or out.startswith('('):
                                collecting_table = False
                                separator_seen = False
                                table_data_str = '\n'.join(table_data_lines)
                                df, metadata = self.parse_output_to_dataframe(table_data_str)
                                if df is not None:
                                    dataframe_list.append(df)
                                    concatenated_df = pd.concat(dataframe_list, ignore_index=True)
                                    self.last_dataframe = concatenated_df
                                    try:
                                        from IPython.display import display
                                        display(concatenated_df)
                                        print(metadata)
                                    except Exception:
                                        print(concatenated_df)
                                        print(metadata)
                                else:
                                    for table_line in table_data_lines:
                                        print(table_line)
                                # Clear the table buffer for the next block
                                table_data_lines = []
                            else:
                                # Still within table block: continue collecting table data
                                table_data_lines.append(out)
                                continue

                        # Process non-table data immediately
                        if out.startswith("/*"):
                            stdout_print_flag = False
                        if stdout_print_flag and out:
                            print(out)
                        if out.startswith("*/"):
                            stdout_print_flag = True

                    for out in proc.stderr:
                        if out.startswith("/*"):
                            error_print_flag = False
                        if error_print_flag and out:
                            print(out)
                        if out.startswith("*/"):
                            error_print_flag = True

                    # End-of-stream: if any table data remains, process it.
                    if table_data_lines and separator_seen:
                        table_data_str = '\n'.join(table_data_lines)
                        df, metadata = self.parse_output_to_dataframe(table_data_str)
                        if df is not None:
                            dataframe_list.append(df)
                            concatenated_df = pd.concat(dataframe_list, ignore_index=True)
                            self.last_dataframe = concatenated_df
                            try:
                                from IPython.display import display
                                display(concatenated_df)
                                print(metadata)
                            except Exception:
                                print(concatenated_df)
                                print(metadata)
                        else:
                            for table_line in table_data_lines:
                                print(table_line)

                total_exec_duration += time.time() - exec_start_time

        except Exception as e:
            print(f"Failed to execute SQL command: {e}")
            raise e
        finally:
            # Clean up batch files if not in debug mode
            if not debug:
                for file in temp_dir.glob("*.sql"):
                    file.unlink()
                temp_dir.rmdir()
            else:
                print(f"\nBatch files preserved in: {temp_dir}")
        if print_timing:
            print(f"\nTotal execution time: {time.time() - start_time:.2f} seconds")
            print(f"SQL execution time: {total_exec_duration:.2f} seconds")

        return

    def get_last_output_as_dataframe(self) -> Optional[pd.DataFrame]:
        """
        Convert the last command output to a DataFrame if possible.
        
        Returns:
            DataFrame or None if the output can't be parsed
        """
        if not self.last_output:
            return None

        df, metadata = self.parse_output_to_dataframe(self.last_output)
        if metadata and not metadata.isspace():
            print(metadata)
        return df


if __name__ == "__main__":
    import urllib.parse
    from pathlib import Path
    from connection import SQLConnection
    from parser import SQLParser

    # Instantiate the SQLConnection class
    connection = SQLConnection()

    # Set the connection string manually (equivalent to your sqlcmd command)
    connection.set_connection_string(
        "mssql+sqlcmd:///?odbc_connect=" +
        urllib.parse.quote("SERVER=localhost;DATABASE=Northwind;UID=sa;PWD=mypassword1234!"))

    # Ensure the connection information is available
    if not connection.connection_info:
        raise ValueError("Failed to parse SQL connection string.")

    # Instantiate the SQLParser with the connection
    parser = SQLParser(connection)

    # Instantiate the SQLExecutor with the connection and parser
    sql_executor = SQLExecutor(connection=connection, parser=parser)

    # SQL file path based on the provided sqlcmd command
    sql_file_path = Path(Path(__file__).parent.parent, "tests", "empty.sql")

    # Read the SQL content from the file
    if sql_file_path.exists():
        with open(sql_file_path, "r", encoding="utf-8") as file:
            sql_content = file.read()
    else:
        raise FileNotFoundError(f"SQL file not found: {sql_file_path}")

    # Execute the SQL content f"""SELECT TOP 5 * FROM Customers;EXECUTE_SQL_FILE '{sql_file_path}'"""
    result_df = sql_executor.execute_sql(f"""EXECUTE_SQL_FILE '{sql_file_path}'""")

    # Display the output DataFrame if available
    if result_df is not None:
        from IPython.display import display
        display(result_df)
