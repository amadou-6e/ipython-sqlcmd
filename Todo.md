Add variable exports
result = %sqlcmd SELECT TOP 1 object_id, name FROM sys.tables ORDER BY name;
Add postgres