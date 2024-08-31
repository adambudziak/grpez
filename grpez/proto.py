from pydantic import BaseModel

from grpez.handler import Handler


def emit_proto_service(svc_name: str, handlers: dict[str, Handler]):
    rpcs = []
    msg_types = set()
    for path, handler in handlers.items():
        msg_types.add(handler.request_type)
        msg_types.add(handler.response_type)
        rpcs.append(
            (
                path,
                ("stream " if handler.rpc_type.startswith("stream") else "") + handler.request_type.__name__,
                ("stream " if handler.rpc_type.endswith("stream") else "") + handler.response_type.__name__,
            )
        )

    svc = f"""
syntax = "proto3";
    
service {svc_name} {{
    {'\n'.join(f'rpc {path}({req}) returns ({ret}) {{}}' for (path, req, ret) in rpcs)}
}}
""".strip()

    messages = "\n\n".join(emit_proto_message(m) for m in msg_types)

    return f"{svc}\n\n{messages}"


def emit_proto_message(m: type[BaseModel]):
    proto_fields = []
    for name, field in m.model_fields.items():
        proto_fields.append((_type_mapping[field.annotation], name))

    return f"""
message {m.__name__} {{
    {'\n'.join(f'{type_} {name_} = {idx};' for idx, (type_, name_) in enumerate(proto_fields, 1))}
}}
""".strip()


_type_mapping = {str: "string", list[str]: "repeated string", int: "int64"}
