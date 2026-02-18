from typing import List, Dict, Any, Optional
from json_logic import jsonLogic
from orgmind.storage.models_access_control import PolicyModel, UserModel

class ABACEngine:
    """
    Attribute-Based Access Control Engine.
    Evaluates JSONLogic policies against request context.
    """

    def evaluate_policy(self, policy: PolicyModel, context: Dict[str, Any]) -> bool:
        """
        Evaluate a single policy's condition against the context.
        Returns True if condition is met.

        Examples of JSONLogic rules:
        
        1. Check if user owns the resource:
           {"==": [{"var": "resource.owner_id"}, {"var": "user.id"}]}

        2. RBAC + Ownership (Admin OR Owner):
           {
             "or": [
               {"in": ["admin", {"var": "user.roles"}]}, 
               {"==": [{"var": "resource.owner_id"}, {"var": "user.id"}]}
             ]
           }

        3. Attribute checks (e.g., Public resource AND View action):
           {
               "and": [
                   {"==": [{"var": "resource.is_public"}, true]},
                   {"==": [{"var": "action"}, "view"]}
               ]
           }

        The context provided to this function typically includes:
        - user: properties of the user (id, email, roles, etc.)
        - resource: properties of the target resource
        - action: the action being performed (read, write, delete)
        """
        try:
            # jsonLogic returns the result of the rule
            result = jsonLogic(policy.condition, context)
            return bool(result)
        except Exception:
            # If evaluation fails, default to False (deny/safe)
            return False

    def check_access(
        self, 
        user: UserModel, 
        resource: str, 
        action: str, 
        policies: List[PolicyModel], 
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if user has access to resource/action based on policies.
        
        Algorithm:
        1. Filter policies matching resource & action.
        2. Sort by priority (descending).
        3. Evaluate conditions.
        4. If a matching policy says 'deny', return False immediately (Deny-Overrides or explicit deny).
        5. If a matching policy says 'allow', store it.
        6. Return True if at least one 'allow' and no 'deny'.
        
        Note: The context should include 'user' with user attributes, 
        and 'resource' with resource attributes.
        """
        if context is None:
            context = {}
            
        # Enrich context with user info
        if "user" not in context:
            context["user"] = {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "roles": [r.name for r in user.roles] if user.roles else []
            }
            
        relevant_policies = [
            p for p in policies 
            if (p.resource == resource or p.resource == "*") and 
               (p.action == action or p.action == "*")
        ]
        
        # Sort by priority desc
        # Assuming priority is string in model but int logic, let's cast or use separate logic
        # Model definition has priority as Mapped[int] but server_default='0' might imply string if not careful.
        # Check model definition: priority: Mapped[int]
        relevant_policies.sort(key=lambda p: int(p.priority) if str(p.priority).isdigit() else 0, reverse=True)
        
        allowed = False
        
        for policy in relevant_policies:
            if self.evaluate_policy(policy, context):
                if policy.effect == "deny":
                    return False
                if policy.effect == "allow":
                    allowed = True
                    
        return allowed
