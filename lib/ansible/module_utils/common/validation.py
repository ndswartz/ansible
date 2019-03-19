# -*- coding: utf-8 -*-
# Copyright (c) 2018 Ansible Project
# Simplified BSD License (see licenses/simplified_bsd.txt or https://opensource.org/licenses/BSD-2-Clause)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.module_utils._text import to_native
from ansible.module_utils.common.collections import is_iterable
from ansible.module_utils.six import string_types


def count_terms(terms, module_parameters):
    """Count the number of occurrences of a key in a given dictionary

    :arg terms: String or iterable of values to check
    :arg module_parameters: Dictionary of module parameters

    :returns: An integer that is the number of occurrences of the terms values
        in the provided dictionary.
    """

    if not is_iterable(terms):
        terms = [terms]

    return len(set(terms).intersection(module_parameters))


def check_mutually_exclusive(terms, module_parameters):
    """Check mutually exclusive terms against argument parameters. Accepts
    a single list or list of lists that are groups of terms that should be
    mutually exclusive with one another

    :arg terms: List of mutually exclusive module parameters
    :arg module_parameters: Dictionary of module parameters

    :returns: Empty list or raises TypeError if the check fails.
    """

    results = []
    if terms is None:
        return results

    for check in terms:
        count = count_terms(check, module_parameters)
        if count > 1:
            results.append(check)

    if results:
        full_list = ['|'.join(check) for check in results]
        msg = "parameters are mutually exclusive: %s" % ', '.join(full_list)
        raise TypeError(to_native(msg))

    return results


def check_required_one_of(terms, module_parameters):
    """Check each list of terms to ensure at least one exists in the given module
    parameters. Accepts a list of lists or tuples.

    :arg terms: List of lists of terms to check. For each list of terms, at
        least one is required.
    :arg module_parameters: Dictionary of module parameters

    :returns: Empty list or raises TypeError if the check fails.
    """

    results = []
    if terms is None:
        return results

    for term in terms:
        count = count_terms(term, module_parameters)
        if count == 0:
            results.append(term)

    if results:
        for term in results:
            msg = "one of the following is required: %s" % ', '.join(term)
            raise TypeError(to_native(msg))

    return results


def check_required_together(terms, module_parameters):
    """Check each list of terms to ensure every parameter in each list exists
    in the given module parameters. Accepts a list of lists or tuples.

    :arg terms: List of lists of terms to check. Each list should include
        parameters that are all required when at least one is specified
        in the module_parameters.
    :arg module_parameters: Dictionary of module parameters

    :returns: Empty list or raises TypeError if the check fails.
    """

    results = []
    if terms is None:
        return results

    for term in terms:
        counts = [count_terms(field, module_parameters) for field in term]
        non_zero = [c for c in counts if c > 0]
        if len(non_zero) > 0:
            if 0 in counts:
                results.append(term)
    if results:
        for term in results:
            msg = "parameters are required together: %s" % ', '.join(term)
            raise TypeError(to_native(msg))

    return results


def check_required_by(requirements, module_parameters):
    """For each key in requirements, check the corresponding list to see if they
    exist in module_parameters. Accepts a single string or list of values for
    each key.

    :arg requirements: Dictionary of requirements
    :arg module_parameters: Dictionary of module parameters

    :returns: Empty dictionary or raises TypeError if the
    """

    result = {}
    if requirements is None:
        return result

    for (key, value) in requirements.items():
        if key not in module_parameters or module_parameters[key] is None:
            continue
        result[key] = []
        # Support strings (single-item lists)
        if isinstance(value, string_types):
            value = [value]
        for required in value:
            if required not in module_parameters or module_parameters[required] is None:
                result[key].append(required)

    if result:
        for key, missing in result.items():
            if len(missing) > 0:
                msg = "missing parameter(s) required by '%s': %s" % (key, ', '.join(missing))
                raise TypeError(to_native(msg))

    return result


def check_required_arguments(argument_spec, module_parameters):
    """Check all paramaters in argument_spec and return a list of parameters
    that are required by not present in module_parameters.

    Raises AnsibleModuleParameterException if the check fails.

    :arg argument_spec: Argument spec dicitionary containing all parameters
        and their specification
    :arg module_paramaters: Dictionary of module parameters

    :returns: Empty list or raises TypeError if the check fails.
    """

    missing = []
    if argument_spec is None:
        return missing

    for (k, v) in argument_spec.items():
        required = v.get('required', False)
        if required and k not in module_parameters:
            missing.append(k)

    if missing:
        msg = "missing required arguments: %s" % ", ".join(missing)
        raise TypeError(to_native(msg))

    return missing


def check_required_if(requirements, module_parameters):
    """Check parameters that are conditionally required.

    Raises TypeError if the check fails.

    :arg requirements: List of lists specifying a parameter, value, parameters
        required when the given parameter is the specified value, and optionally
        a boolean indicating any or all parameters are required.

        Example:
            required_if=[
                ['state', 'present', ('path',), True],
                ['someint', 99, ('bool_param', 'string_param')],
            ]

    :arg module_paramaters: Dictionary of module parameters

    :returns: Empty list or raises TypeError if the check fails.
        The results attribute of the exception contains a list of dictionaries.
        Each dictionary is the result of evaluting each item in requirements.
        Each return dictionary contains the following keys:

            :key missing: List of parameters that are required but missing
            :key requires: 'any' or 'all'
            :key paramater: Parameter name that has the requirement
            :key value: Original value of the paramater
            :key requirements: Original required parameters

        Example:
            [
                {
                    'parameter': 'someint',
                    'value': 99
                    'requirements': ('bool_param', 'string_param'),
                    'missing': ['string_param'],
                    'requires': 'all',
                }
            ]

    """
    results = []
    if requirements is None:
        return results

    for req in requirements:
        missing = {}
        missing['missing'] = []
        max_missing_count = 0
        is_one_of = False
        if len(req) == 4:
            key, val, requirements, is_one_of = req
        else:
            key, val, requirements = req

        # is_one_of is True at least one requirement should be
        # present, else all requirements should be present.
        if is_one_of:
            max_missing_count = len(requirements)
            missing['requires'] = 'any'
        else:
            missing['requires'] = 'all'

        if key in module_parameters and module_parameters[key] == val:
            for check in requirements:
                count = count_terms(check, module_parameters)
                if count == 0:
                    missing['missing'].append(check)
        if len(missing['missing']) and len(missing['missing']) >= max_missing_count:
            missing['parameter'] = key
            missing['value'] = val
            missing['requirements'] = requirements
            results.append(missing)

    if results:
        for missing in results:
            msg = "%s is %s but %s of the following are missing: %s" % (
                missing['parameter'], missing['value'], missing['requires'], ', '.join(missing['missing']))
            raise TypeError(to_native(msg))

    return results


def check_missing_parameters(module_parameters, required_parameters=None):
    """This is for checking for required params when we can not check via
    argspec because we need more information than is simply given in the argspec.

    :arg module_paramaters: Dictionary of module parameters
    :arg required_parameters: List of parameters to look for in the given module
        parameters

    :returns: Empty list or raises TypeError if the check fails.
    """
    missing_params = []
    if required_parameters is None:
        return missing_params

    for param in required_parameters:
        if not module_parameters.get(param):
            missing_params.append(param)

    if missing_params:
        msg = "missing required arguments: %s" % ', '.join(missing_params)
        raise TypeError(to_native(msg))

    return missing_params
