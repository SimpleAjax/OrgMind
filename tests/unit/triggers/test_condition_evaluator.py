from orgmind.triggers.engine.evaluator import ConditionEvaluator
import pytest

@pytest.fixture
def evaluator():
    return ConditionEvaluator()

def test_simple_equality(evaluator):
    condition = {"==": [{"var": "status"}, "active"]}
    data = {"status": "active"}
    assert evaluator.evaluate(condition, data) is True
    
    data_bad = {"status": "inactive"}
    assert evaluator.evaluate(condition, data_bad) is False

def test_nested_access(evaluator):
    condition = {">": [{"var": "metrics.count"}, 10]}
    
    data_pass = {"metrics": {"count": 15}}
    data_fail = {"metrics": {"count": 5}}
    
    # Check if dot notation works
    # Standard python json-logic implementation supports dot notation if var names contain them
    # OR nested access via separate logic. Let's see if library supports `metrics.count`
    # If not, we might need a custom data accessor or ensure data is flat?
    # Actually, json-logic-py uses python's dictionary get which doesn't recurse by default for strings with dots.
    # We might need to handle dot notation explicitly if the library doesn't.
    # Let's verify with a test - if fail, we fix evaluator.
    
    # Wait, json-logic-py supports dot notation if using specific accessor logic?
    # The README for json-logic-py says:
    # "If you like, you can subclass Rule and override variable(self, data, var_name) to inspect data..."
    # If json-logic-quibble is used (which seems so), it might handle it?
    
    # Let's try standard way first.
    pass # We will see if it fails

def test_logic_operators(evaluator):
    condition = {
        "and": [
            {">": [{"var": "age"}, 18]},
            {"==": [{"var": "status"}, "active"]}
        ]
    }
    
    data_pass = {"age": 20, "status": "active"}
    data_fail_age = {"age": 15, "status": "active"}
    data_fail_status = {"age": 20, "status": "inactive"}
    
    assert evaluator.evaluate(condition, data_pass) is True
    assert evaluator.evaluate(condition, data_fail_age) is False
    assert evaluator.evaluate(condition, data_fail_status) is False

def test_in_operator(evaluator):
    condition = {"in": [{"var": "role"}, ["admin", "editor"]]}
    
    assert evaluator.evaluate(condition, {"role": "admin"}) is True
    assert evaluator.evaluate(condition, {"role": "viewer"}) is False

def test_missing_data(evaluator):
    # Rule expects 'status', data is empty
    condition = {"==": [{"var": "status"}, "active"]}
    data = {}
    # None == "active" is False
    assert evaluator.evaluate(condition, data) is False

def test_dot_notation_support(evaluator):
    """
    Separate test for nested access to confirm support or need for fix.
    """
    condition = {"==": [{"var": "user.role"}, "admin"]}
    data = {"user": {"role": "admin"}}
    
    # If this fails, we need to implement dot notation support in evaluator
    assert evaluator.evaluate(condition, data) is True
