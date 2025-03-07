class SQLExecutionError(Exception):
    """Custom error for SQL execution failures with clean formatting and line number detection"""

    ERROR_PATTERN = r"Msg (\d+), Level (\d+), State (\d+), Server ([^,]+), Line (\d+)\s*(.+)"

    def __init__(self, sql_error: str, model_name: str, sql_script: str):
        self.model_name = model_name
        self.sql_script = sql_script
        self.sql_error = str(sql_error)
        self.parsed_error = self._parse_sql_error()
        self.line_number = self.parsed_error.get('line') or self._find_line_number()
        self.clean_error = self.parsed_error.get('message') or self._clean_sql_error()
        super().__init__(self.__str__())

    def _parse_sql_error(self) -> dict:
        """Parse SQL Server specific error format"""
        import re
        match = re.search(self.ERROR_PATTERN, self.sql_error)
        if match:
            return {
                'msg_number': int(match.group(1)),
                'level': int(match.group(2)),
                'state': int(match.group(3)),
                'server': match.group(4),
                'line': int(match.group(5)),
                'message': match.group(6).strip()
            }
        return {}

    def _clean_sql_error(self) -> str:
        """Extract just the SQL Server error message"""
        # For SQL Server errors, extract message between '][SQL Server]' and '('
        if '[SQL Server]' in self.sql_error:
            return self.sql_error.split('[SQL Server]')[1].split('(')[0].strip()
        return self.sql_error

    def _find_line_number(self) -> int:
        """Try to extract line number from SQL error and script context"""
        try:
            # If error mentions an object, try to find it in the script
            if 'Invalid object name' in self.sql_error:
                object_name = self.sql_error.split("'")[1]
                lines = self.sql_script.split('\n')
                for i, line in enumerate(lines, 1):
                    if object_name in line:
                        return i

            # Check for syntax error patterns
            if 'Incorrect syntax near' in self.sql_error:
                error_token = self.sql_error.split("'")[1]
                lines = self.sql_script.split('\n')
                for i, line in enumerate(lines, 1):
                    if error_token in line:
                        return i

        except Exception:
            pass
        return None

    def get_error_context(self, context_lines: int = 3) -> str:
        """Get the SQL script context around the error line"""
        if not self.line_number:
            return ""

        lines = self.sql_script.split('\n')
        start = max(0, self.line_number - context_lines - 1)
        end = min(len(lines), self.line_number + context_lines)

        context = []
        for i in range(start, end):
            prefix = '-> ' if i == self.line_number - 1 else '   '
            context.append(f"{prefix}{i+1:4d} | {lines[i]}")

        return '\n'.join(context)

    def __str__(self) -> str:
        """Format error message with context"""
        error_parts = []

        if self.parsed_error:
            error_parts.append(f"SQL Error [Model: {self.model_name}]")
            error_parts.append(f"Message {self.parsed_error['msg_number']}: {self.clean_error}")
            error_parts.append(f"Severity: {self.parsed_error['level']}")
            error_parts.append(f"State: {self.parsed_error['state']}")
            error_parts.append(f"Server: {self.parsed_error['server']}")
            if self.line_number:
                error_parts.append(f"Line: {self.line_number}")
        else:
            error_parts.append(f"SQL Error in {self.model_name}: {self.clean_error}")
            if self.line_number:
                error_parts.append(f"At line: {self.line_number}")

        # Add code context if line number is available
        context = self.get_error_context()
        if context:
            error_parts.append("\nCode context:")
            error_parts.append(context)

        return '\n'.join(error_parts)
