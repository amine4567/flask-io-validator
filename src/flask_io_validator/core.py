import inspect
from functools import wraps
from typing import Callable

import pydantic
from flask import request

from .consts import REQUEST_ARGS_KWARG, REQUEST_BODY_PARAM, RESERVED_KWARGS
from .exceptions import (
    MissingParameterError,
    MissingTypeHintError,
    MissingURLVariableError,
    ReservedKeywordError,
)
from .schemas import APICallError, ErrorType, StrictBaseModel


def validate_url_vars(decorated_f: Callable) -> Callable:
    """Decorator to apply on flask view functions to validate an API's call URL
    variables.

    Every parameter that is not a reserved keyword is considered an URL variable, there
    must be a one-to-one correspondence between the declared URL variables and the
    declared view function parameters.

    Each parameter must be type hinted.

    Parameters
    ----------
    decorated_f : Callable
        Decorated function

    Returns
    -------
    Callable
        Transformed function

    Raises
    ------
    ReservedKeywordsError
        if reserved keywords are used as URL variables
    MissingParametersError
        if declared URL variables are missing from the function's parameters
    MissingURLVariableError
        if a declared function parameter doesn't have a corresponding URL variable
    MissingTypeHintsError
        if a parameter is missing a type hint
    """

    @wraps(decorated_f)
    def transformed_f(*args, **kwargs):
        declared_url_vars = request.url_rule.arguments
        illegal_url_vars = declared_url_vars.intersection(RESERVED_KWARGS)
        if len(illegal_url_vars) != 0:
            raise ReservedKeywordError(
                f"{illegal_url_vars} are reserved keywords and cannot be used as URL "
                "variables."
            )

        non_reserved_params = set(
            inspect.signature(decorated_f).parameters.keys()
        ) - set(RESERVED_KWARGS)
        if len(declared_url_vars - non_reserved_params) != 0:
            raise MissingParameterError(
                f"{declared_url_vars - non_reserved_params} are declared as URL "
                f"variables but are missing in {decorated_f}'s parameters."
            )

        if len(non_reserved_params - declared_url_vars) != 0:
            raise MissingURLVariableError(
                f"{non_reserved_params - declared_url_vars} are declared in the "
                f"{decorated_f}'s parameters but are not declared as URL variables."
            )

        annotated_params = {
            k: (v, ...)
            for k, v in decorated_f.__annotations__.items()
            if k not in RESERVED_KWARGS
        }
        missing_annotations = declared_url_vars - set(annotated_params.keys())
        if len(missing_annotations) != 0:
            raise MissingTypeHintError(
                f"{missing_annotations} are declared as URL variables, exist in the "
                f"{decorated_f}'s parameters but are missing annotations. Please add "
                "type hints to these parameters."
            )

        try:
            UrlVarsModel = pydantic.create_model(
                "UrlVarsModel", __base__=StrictBaseModel, **annotated_params
            )
            url_vars_values = request.view_args

            validated_values = UrlVarsModel(**url_vars_values)
        except pydantic.ValidationError as e:
            return (
                [
                    APICallError(
                        type=ErrorType.VALIDATION,
                        subtype=error["type"],
                        message=".".join(error["loc"]) + ": " + error["msg"],
                    )
                    for error in e.errors()
                ],
                400,
            )

        new_kwargs = {**kwargs, **validated_values.dict()}
        return decorated_f(*args, **new_kwargs)

    return transformed_f


def validate_request_vals(
    param_name: str, request_vals_getter: Callable[[], dict]
) -> Callable:
    def decorator(decorated_f: Callable) -> Callable:
        @wraps(decorated_f)
        def transformed_f(*args, **kwargs):
            if param_name in inspect.signature(decorated_f).parameters:
                try:
                    Schema = decorated_f.__annotations__[param_name]
                except KeyError:
                    raise MissingTypeHintError(
                        f"The '{param_name}' parameter not found in {decorated_f}'s "
                        "annotations. Please add a type hint. "
                    )

                if not issubclass(Schema, pydantic.BaseModel):
                    raise TypeError(
                        f"The '{param_name}' parameter expected to be of type "
                        f"{pydantic.BaseModel} but got {Schema}."
                    )

                try:
                    request_vals = Schema(**request_vals_getter())
                except pydantic.ValidationError as e:
                    return (
                        [
                            APICallError(
                                type=ErrorType.VALIDATION,
                                subtype=error["type"],
                                message=".".join(error["loc"]) + ": " + error["msg"],
                            )
                            for error in e.errors()
                        ],
                        400,
                    )

                new_kwargs = {**kwargs, param_name: request_vals}
            else:
                try:
                    StrictBaseModel(**request_vals_getter())
                except pydantic.ValidationError:
                    return (
                        APICallError(
                            type=ErrorType.VALIDATION,
                            message=f"{param_name} is expected to be empty but got "
                            + str(request_vals_getter()),
                        ),
                        400,
                    )

                new_kwargs = kwargs

            return decorated_f(*args, **new_kwargs)

        return transformed_f

    return decorator


validate_request_body = validate_request_vals(
    REQUEST_BODY_PARAM, lambda: request.get_json() or dict()
)
validate_request_body.__doc__ = """
Decorator to apply on flask view functions to validate an API's call request body.

Parameters
----------
decorated_f : Callable
    Decorated function

Returns
-------
Callable
    Transformed function

Raises
------
MissingTypeHintError
    _description_
TypeError
    _description_
"""

validate_request_args = validate_request_vals(
    REQUEST_ARGS_KWARG, lambda: dict(request.args)
)
validate_request_args.__doc__ = """
Decorator to apply on flask view functions to validate an API's call request arguments.

Parameters
----------
decorated_f : Callable
    Decorated function

Returns
-------
Callable
    Transformed function

Raises
------
MissingTypeHintError
    _description_
TypeError
    _description_
"""
