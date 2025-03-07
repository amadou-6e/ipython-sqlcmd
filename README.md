# SQL Command Magic for IPython

An IPython magic extension for executing SQL queries against Microsoft SQL Server using the `sqlcmd` utility.

## Features

- Execute SQL queries directly from IPython/Jupyter notebooks
- Connect to Microsoft SQL Server using simple parameters or connection strings
- Execute SQL in batches separated by GO statements
- Execute external SQL files using EXECUTE_SQL_FILE
- Substitute Python variables in SQL queries
- Debug mode for troubleshooting

## Installation

```bash
pip install sqlcmd-magic
```

## Requirements

- Python 3.7+
- IPython 7.0+
- Pandas 1.0+
- Microsoft SQL Server
- `sqlcmd` utility installed and available in PATH

## Usage

### Load the extension

```python
%load_ext sqlcmd
```

### Set connection using simplified syntax

```python
# Connect using just the database name (uses defaults for other parameters)
%sqlcmd AdventureWorks

# Connect with custom server, username and password
%sqlcmd AdventureWorks --server=myserver --username=myuser --password=mypassword

# Connect using password from environment variable
%sqlcmd AdventureWorks --password-env=MY_SQL_PASSWORD

# Connect with additional connection options
%sqlcmd AdventureWorks --driver="ODBC Driver 18 for SQL Server" --no-encrypt
```

### Set connection using full connection string (advanced)

```python
%sqlcmd 'mssql+sqlcmd:///?odbc_connect=SERVER=myserver;DATABASE=mydb;UID=myuser;PWD=mypassword'
```

### Execute SQL

```python
%%sqlcmd
SELECT TOP 10 *
FROM MyTable
WHERE Column1 = 'Value'
```

### Execute SQL with variable substitution

```python
value = "SomeValue"

%%sqlcmd
SELECT TOP 10 *
FROM MyTable
WHERE Column1 = '$value'
```

### Debug mode

```python
%%sqlcmd --debug
SELECT TOP 10 *
FROM MyTable
```

### Execute SQL from file

```python
%%sqlcmd
EXECUTE_SQL_FILE 'path/to/query.sql'
```

## Connection Parameters

When using the simplified connection syntax, the following parameters are available:


| Parameter         | Short Flag | Default Value | Description |
|------------------|------------|---------------|-------------|
| `--server`       | `-s`       | localhost     | SQL Server instance |
| `--username`     | `-u`       | sa            | SQL Server username |
| `--password`     | `-p`       | None          | SQL Server password |
| `--password-env` | `-e`       | SSMS_PASSWORD | Environment variable containing password |
| `--driver`       | `-d`       | ODBC Driver 17 for SQL Server | ODBC driver name |
| `--encrypt`      |            | True          | Encrypt connection (default) |
| `--no-encrypt`   |            |               | Do not encrypt connection |
| `--trust-certificate` |       | True          | Trust server certificate (default) |
| `--no-trust-certificate` |    |               | Do not trust server certificate |
| `--encoding`     | `-c`       | utf-8         | Output and SQL database encoding (e.g., `utf-8`, `latin-1`, `cp1252`) |
| `--show-execution-time` | `-t` | False        | Print execution time of SQL queries |

## License

MIT