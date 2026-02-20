#!/usr/bin/env python3
"""
OrgMind PM Configuration Loader

This script loads the Project Management configuration files into OrgMind:
- Object Types (entity schemas)
- Link Types (relationship schemas)
- Triggers (event-driven rules)

Usage:
    python load_config.py [--reset] [--verify]

Options:
    --reset    Drop existing PM tables before loading (DESTRUCTIVE)
    --verify   Run verification tests after loading
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

# Add OrgMind to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from orgmind.storage.postgres_adapter import PostgresAdapter
from orgmind.storage.models import ObjectTypeModel, LinkTypeModel
from orgmind.platform.config import settings


class ConfigLoader:
    """Loads PM configuration into OrgMind."""
    
    def __init__(self, postgres: PostgresAdapter):
        self.postgres = postgres
        self.config_dir = Path(__file__).parent.parent / "config"
        self.results = {
            "object_types": {"created": 0, "updated": 0, "errors": []},
            "link_types": {"created": 0, "updated": 0, "errors": []},
            "triggers": {"created": 0, "errors": []},
        }
    
    def load_yaml(self, filename: str) -> Dict:
        """Load YAML configuration file."""
        filepath = self.config_dir / filename
        print(f"\n📄 Loading {filepath.name}...")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    async def load_object_types(self, reset: bool = False) -> bool:
        """Load Object Types into OrgMind."""
        config = self.load_yaml("object_types.yaml")
        object_types = config.get("object_types", [])
        
        print(f"   Found {len(object_types)} object types to configure")
        
        with self.postgres.get_session() as session:
            if reset:
                print("   ⚠️  Reset mode: Deleting existing PM object types...")
                # Soft delete - mark as archived
                for ot in session.query(ObjectTypeModel).all():
                    if ot.id.startswith("ot_"):
                        ot.status = "archived"
                session.commit()
            
            for obj_type in object_types:
                try:
                    result = await self._create_or_update_object_type(session, obj_type)
                    if result == "created":
                        self.results["object_types"]["created"] += 1
                    else:
                        self.results["object_types"]["updated"] += 1
                except Exception as e:
                    error_msg = f"Failed to load {obj_type.get('id', 'unknown')}: {str(e)}"
                    print(f"   ❌ {error_msg}")
                    self.results["object_types"]["errors"].append(error_msg)
            
            session.commit()
        
        return len(self.results["object_types"]["errors"]) == 0
    
    async def _create_or_update_object_type(self, session, obj_type: Dict) -> str:
        """Create or update a single object type."""
        type_id = obj_type["id"]
        
        # Check if exists
        existing = session.query(ObjectTypeModel).filter_by(id=type_id).first()
        
        # Prepare properties JSON
        properties = obj_type.get("properties", {})
        
        # Add validation info to properties
        validation = obj_type.get("validation_rules", [])
        if validation:
            properties["_validation"] = validation
        
        if existing:
            # Update
            existing.name = obj_type["name"]
            existing.description = obj_type.get("description", "")
            existing.properties = properties
            existing.implements = obj_type.get("implements", [])
            existing.sensitive_properties = obj_type.get("sensitive_properties", [])
            existing.version += 1
            print(f"   🔄 Updated: {type_id}")
            return "updated"
        else:
            # Create
            new_type = ObjectTypeModel(
                id=type_id,
                name=obj_type["name"],
                description=obj_type.get("description", ""),
                properties=properties,
                implements=obj_type.get("implements", []),
                sensitive_properties=obj_type.get("sensitive_properties", []),
                default_permissions=obj_type.get("default_permissions"),
            )
            session.add(new_type)
            print(f"   ✅ Created: {type_id}")
            return "created"
    
    async def load_link_types(self, reset: bool = False) -> bool:
        """Load Link Types into OrgMind."""
        config = self.load_yaml("link_types.yaml")
        link_types = config.get("link_types", [])
        
        print(f"   Found {len(link_types)} link types to configure")
        
        with self.postgres.get_session() as session:
            if reset:
                print("   ⚠️  Reset mode: Deleting existing PM link types...")
                for lt in session.query(LinkTypeModel).all():
                    if lt.id.startswith("lt_"):
                        session.delete(lt)
                session.commit()
            
            for link_type in link_types:
                try:
                    result = await self._create_or_update_link_type(session, link_type)
                    if result == "created":
                        self.results["link_types"]["created"] += 1
                    else:
                        self.results["link_types"]["updated"] += 1
                except Exception as e:
                    error_msg = f"Failed to load {link_type.get('id', 'unknown')}: {str(e)}"
                    print(f"   ❌ {error_msg}")
                    self.results["link_types"]["errors"].append(error_msg)
            
            session.commit()
        
        return len(self.results["link_types"]["errors"]) == 0
    
    async def _create_or_update_link_type(self, session, link_type: Dict) -> str:
        """Create or update a single link type."""
        type_id = link_type["id"]
        
        # Check if exists
        existing = session.query(LinkTypeModel).filter_by(id=type_id).first()
        
        if existing:
            # Update
            existing.name = link_type["name"]
            existing.description = link_type.get("description", "")
            existing.source_type = link_type["source_type"]
            existing.target_type = link_type["target_type"]
            existing.cardinality = link_type.get("cardinality", "many_to_many")
            existing.properties = link_type.get("properties", {})
            print(f"   🔄 Updated: {type_id}")
            return "updated"
        else:
            # Create
            new_type = LinkTypeModel(
                id=type_id,
                name=link_type["name"],
                description=link_type.get("description", ""),
                source_type=link_type["source_type"],
                target_type=link_type["target_type"],
                cardinality=link_type.get("cardinality", "many_to_many"),
                properties=link_type.get("properties", {}),
            )
            session.add(new_type)
            print(f"   ✅ Created: {type_id}")
            return "created"
    
    async def load_triggers(self) -> bool:
        """Load Triggers into OrgMind."""
        config = self.load_yaml("triggers.yaml")
        
        event_triggers = config.get("event_triggers", [])
        scheduled_triggers = config.get("scheduled_triggers", [])
        all_triggers = event_triggers + scheduled_triggers
        
        print(f"   Found {len(all_triggers)} triggers to configure")
        print(f"     - Event-driven: {len(event_triggers)}")
        print(f"     - Scheduled: {len(scheduled_triggers)}")
        
        # Note: Trigger loading depends on OrgMind's trigger service
        # This is a placeholder - actual implementation depends on OrgMind's API
        print("\n⚠️  Triggers are loaded separately via OrgMind Trigger API")
        print("   See: POST /api/v1/rules")
        
        # Store triggers in a separate file for manual loading
        triggers_export = self.config_dir / "triggers_export.json"
        with open(triggers_export, 'w') as f:
            json.dump({
                "event_triggers": event_triggers,
                "scheduled_triggers": scheduled_triggers,
            }, f, indent=2)
        print(f"   💾 Exported triggers to: {triggers_export}")
        
        self.results["triggers"]["created"] = len(all_triggers)
        return True
    
    def print_summary(self):
        """Print loading summary."""
        print("\n" + "=" * 70)
        print("CONFIGURATION LOADING SUMMARY")
        print("=" * 70)
        
        print("\n📊 Object Types:")
        print(f"   Created: {self.results['object_types']['created']}")
        print(f"   Updated: {self.results['object_types']['updated']}")
        if self.results["object_types"]["errors"]:
            print(f"   ❌ Errors: {len(self.results['object_types']['errors'])}")
            for error in self.results["object_types"]["errors"][:5]:
                print(f"      - {error}")
        
        print("\n🔗 Link Types:")
        print(f"   Created: {self.results['link_types']['created']}")
        print(f"   Updated: {self.results['link_types']['updated']}")
        if self.results["link_types"]["errors"]:
            print(f"   ❌ Errors: {len(self.results['link_types']['errors'])}")
            for error in self.results["link_types"]["errors"][:5]:
                print(f"      - {error}")
        
        print("\n⚡ Triggers:")
        print(f"   Exported: {self.results['triggers']['created']}")
        print("   Note: Load triggers via OrgMind Trigger API")
        
        total_errors = (
            len(self.results["object_types"]["errors"]) +
            len(self.results["link_types"]["errors"])
        )
        
        print("\n" + "=" * 70)
        if total_errors == 0:
            print("✅ Configuration loaded successfully!")
        else:
            print(f"⚠️  Configuration loaded with {total_errors} errors")
        print("=" * 70)
        
        return total_errors == 0


class ConfigVerifier:
    """Verifies the loaded configuration."""
    
    def __init__(self, postgres: PostgresAdapter):
        self.postgres = postgres
    
    async def verify(self) -> bool:
        """Run verification tests."""
        print("\n" + "=" * 70)
        print("CONFIGURATION VERIFICATION")
        print("=" * 70)
        
        tests = [
            self._test_object_types_exist,
            self._test_link_types_exist,
            self._test_crud_operations,
            self._test_relationships,
        ]
        
        all_passed = True
        for test in tests:
            try:
                passed = await test()
                if not passed:
                    all_passed = False
            except Exception as e:
                print(f"   ❌ Test failed with exception: {e}")
                all_passed = False
        
        print("\n" + "=" * 70)
        if all_passed:
            print("✅ All verification tests passed!")
        else:
            print("❌ Some verification tests failed")
        print("=" * 70)
        
        return all_passed
    
    async def _test_object_types_exist(self) -> bool:
        """Test that all object types exist in database."""
        print("\n🧪 Test: Object Types Exist")
        
        expected_types = [
            "ot_customer", "ot_project", "ot_sprint", "ot_task", "ot_person",
            "ot_skill", "ot_assignment", "ot_leave_period", "ot_nudge",
            "ot_sprint_task", "ot_person_skill", "ot_productivity_profile"
        ]
        
        with self.postgres.get_session() as session:
            from orgmind.storage.models import ObjectTypeModel
            existing = {ot.id for ot in session.query(ObjectTypeModel).all()}
            
            missing = [ot for ot in expected_types if ot not in existing]
            
            if missing:
                print(f"   ❌ Missing object types: {missing}")
                return False
            else:
                print(f"   ✅ All {len(expected_types)} object types exist")
                return True
    
    async def _test_link_types_exist(self) -> bool:
        """Test that all link types exist in database."""
        print("\n🧪 Test: Link Types Exist")
        
        expected_links = [
            "lt_customer_has_project", "lt_project_has_task", "lt_task_assigned_to",
            "lt_task_blocks", "lt_person_has_skill"
        ]
        
        with self.postgres.get_session() as session:
            from orgmind.storage.models import LinkTypeModel
            existing = {lt.id for lt in session.query(LinkTypeModel).all()}
            
            missing = [lt for lt in expected_links if lt not in existing]
            
            if missing:
                print(f"   ❌ Missing link types: {missing}")
                return False
            else:
                print(f"   ✅ All key link types exist")
                return True
    
    async def _test_crud_operations(self) -> bool:
        """Test basic CRUD operations."""
        print("\n🧪 Test: CRUD Operations")
        
        try:
            with self.postgres.get_session() as session:
                from orgmind.storage.models import ObjectModel
                from uuid import uuid4
                
                # Create test customer
                test_customer = ObjectModel(
                    id=f"test_customer_{uuid4().hex[:8]}",
                    type_id="ot_customer",
                    data={
                        "name": "Test Customer",
                        "tier": "tier_2",
                        "status": "active"
                    }
                )
                session.add(test_customer)
                session.commit()
                
                # Read
                found = session.query(ObjectModel).filter_by(id=test_customer.id).first()
                if not found:
                    print("   ❌ Failed to read created object")
                    return False
                
                # Update
                found.data["name"] = "Updated Customer"
                session.commit()
                
                # Delete (soft)
                found.status = "deleted"
                session.commit()
                
                print("   ✅ CRUD operations working")
                return True
                
        except Exception as e:
            print(f"   ❌ CRUD test failed: {e}")
            return False
    
    async def _test_relationships(self) -> bool:
        """Test relationship creation."""
        print("\n🧪 Test: Relationships")
        
        try:
            with self.postgres.get_session() as session:
                from orgmind.storage.models import ObjectModel, LinkModel
                from uuid import uuid4
                
                # Create test objects
                customer_id = f"test_cust_{uuid4().hex[:8]}"
                project_id = f"test_proj_{uuid4().hex[:8]}"
                
                customer = ObjectModel(
                    id=customer_id,
                    type_id="ot_customer",
                    data={"name": "Test Customer", "tier": "tier_2"}
                )
                project = ObjectModel(
                    id=project_id,
                    type_id="ot_project",
                    data={"name": "Test Project", "status": "planning"}
                )
                session.add_all([customer, project])
                session.commit()
                
                # Create link
                link = LinkModel(
                    id=f"test_link_{uuid4().hex[:8]}",
                    type_id="lt_customer_has_project",
                    source_id=customer_id,
                    target_id=project_id,
                    data={}
                )
                session.add(link)
                session.commit()
                
                print("   ✅ Relationship creation working")
                return True
                
        except Exception as e:
            print(f"   ❌ Relationship test failed: {e}")
            return False


async def main():
    parser = argparse.ArgumentParser(
        description="Load OrgMind PM Configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python load_config.py              # Load all configs
    python load_config.py --reset      # Reset and reload
    python load_config.py --verify     # Load and verify
    python load_config.py --reset --verify  # Full reset and verify
        """
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing PM tables before loading (DESTRUCTIVE)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run verification tests after loading"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("ORGMIND PM CONFIGURATION LOADER")
    print("=" * 70)
    
    # Initialize database connection
    print("\n🔌 Connecting to database...")
    postgres = PostgresAdapter(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
    )
    
    # Load configurations
    loader = ConfigLoader(postgres)
    
    success = True
    
    # Load Object Types
    if not await loader.load_object_types(reset=args.reset):
        success = False
    
    # Load Link Types
    if not await loader.load_link_types(reset=args.reset):
        success = False
    
    # Load Triggers
    if not await loader.load_triggers():
        success = False
    
    # Print summary
    loader.print_summary()
    
    # Run verification if requested
    if args.verify:
        verifier = ConfigVerifier(postgres)
        if not await verifier.verify():
            success = False
    
    # Exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
