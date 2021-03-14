# Default is JSON Schema Specification
generation_fields = {
    "default": {
        "bool": "boolean",
        "Date": "date",
        "dateTime": "date-time",
        "decimal": "number",
        "Decimal": "number",
        "enum": "enum",
        "int": "integer",
        "bigint": "integer",
        "Integer": "integer",
        "long": "integer",
        "String": "string",
        "str": "string",
    },
    "spring data rest": {
        "boolean": "boolean",
        "date": "Date",
        "dateTime": "DateTime",
        "decimal": "Double",
        "enum": "String",
        "int": "int",
        "bigint": "int",
        "integer": "int",
        "long": "int",
        "string": "String",
    },
    "django": {
        "boolean": "BooleanField",
        "int": "IntegerField",
        "bigint": "BigIntegerField",
        "decimal": "DecimalField",
        "string": "CharField",
        "str": "CharField",
        "String": "CharField",
        "text": "TextField",
        "duration": "DurationField",
        "file": "FileField",
        "float": "FloatField",
        "date": "DateField",
        "dateTime": "DateTimeField",
    },
    "marshmallow": {
        "boolean": "Boolean",
        "int": "Integer",
        "integer": "Integer",
        "bigint": "Integer",
        "decimal": "Decimal",
        "string": "String",
        "text": "Text",
        "duration": "Duration",
        "file": "File",
        "float": "Float",
        "date": "Date",
        "dateTime": "DateTime",
        "date_time": "DateTime",
    },
    "sqlalchemy": {
        "boolean": "Boolean",
        "int": "Integer",
        "integer": "Integer",
        "string": "String",
        "decimal": "Numeric",
        "Decimal": "Numeric",
        "float": "Float",
        "date": "Date",
        "dateTime": "DateTime",
        "date_time": "DateTime",
    },
    "python": {
        "Integer": "int",
        "String": "str",
        "string": "str",
        "Float": "float",
        "Numeric": "Decimal",
        "Boolean": "bool",
    }
}
