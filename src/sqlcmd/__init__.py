"""
SQL Command Magic for IPython.

This package provides a magic command for IPython that allows executing SQL queries 
using sqlcmd against Microsoft SQL Server.
"""

from .exceptions import SQLExecutionError
from .magic import SQLCmdMagic, load_ipython_extension

__all__ = ['SQLExecutionError', 'SQLCmdMagic', 'load_ipython_extension']