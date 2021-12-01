from typing import Any
from collections.abc import Mapping
from graphql.type import (
    GraphQLField,
    GraphQLObjectType,
    GraphQLResolveInfo,
    GraphQLSchema,
)
from ariadne.types import Resolver, SchemaBindable

from .srprocmng import SrProtocol

class SrResolversSetter(SchemaBindable):
    def bind_to_schema(self, schema: GraphQLSchema) -> None:
        for type_object in schema.type_map.values():
            if isinstance(type_object, GraphQLObjectType):
                self.add_resolvers_to_object_fields(type_object)

    def add_resolvers_to_object_fields(self, type_object) -> None:
        for field_name, field_object in type_object.fields.items():
            self.add_resolver_to_field(field_name, field_object)

    def add_resolver_to_field(self, _: str, field_object: GraphQLField) -> None:
        if field_object.resolve is None:
            field_object.resolve = field_resolver
    
def field_resolver(source: Any, info: GraphQLResolveInfo, **args: Any) -> Any:
    field_name = info.field_name
    
    #ATTENTION: Custom condition
    if isinstance(source, SrProtocol):
        source = source._state
    
    value = (
        source.get(field_name)
        if isinstance(source, Mapping)
        else getattr(source, field_name, None)
    )
    if callable(value):
        return value(info, **args)
    return value

srResolver = SrResolversSetter()
