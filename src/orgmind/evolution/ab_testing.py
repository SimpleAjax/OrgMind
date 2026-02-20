import logging
import hashlib
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import select

from orgmind.evolution.models import (
    ABExperimentModel, ABVariantModel, ExperimentAssignmentModel, ABExperimentStatus
)

logger = logging.getLogger(__name__)

class ABTestingService:
    """
    Manages A/B tests, assigning users to variants and tracking conversions.
    """
    
    def create_experiment(
        self, 
        session: Session, 
        name: str, 
        description: str,
        experiment_type: str,
        variants_config: List[Dict[str, Any]]
    ) -> ABExperimentModel:
        """
        Creates a new experiment with defined variants.
        variants_config example:
        [
            {"name": "Control", "weight": 50, "config": {}},
            {"name": "Treatment", "weight": 50, "config": {"policy_enabled": True}}
        ]
        """
        experiment = ABExperimentModel(
            name=name,
            description=description,
            experiment_type=experiment_type,
            status=ABExperimentStatus.DRAFT
        )
        session.add(experiment)
        session.flush() # get ID
        
        for v_conf in variants_config:
            variant = ABVariantModel(
                experiment_id=experiment.id,
                name=v_conf["name"],
                weight=v_conf.get("weight", 50),
                config=v_conf.get("config", {})
            )
            session.add(variant)
            
        return experiment

    def get_assigned_variant(
        self, 
        session: Session, 
        experiment_name: str, 
        entity_id: str
    ) -> Optional[ABVariantModel]:
        """
        Returns the variant assigned to the entity for the given experiment.
        Assignments are persistent once made.
        """
        # 1. Find experiment
        experiment = session.scalar(
            select(ABExperimentModel).where(ABExperimentModel.name == experiment_name)
        )
        if not experiment or experiment.status != ABExperimentStatus.RUNNING:
            return None
            
        # 2. Check existing assignment
        assignment = session.scalar(
            select(ExperimentAssignmentModel).where(
                ExperimentAssignmentModel.experiment_id == experiment.id,
                ExperimentAssignmentModel.entity_id == entity_id
            )
        )
        
        if assignment:
            return session.get(ABVariantModel, assignment.variant_id)
            
        # 3. Assign new variant (Deterministic Hashing)
        # We use a hash of (experiment_id + entity_id) to ensure consistency even without DB lookups logic,
        # but here we persist it for tracking.
        variant = self._assign_variant_logic(experiment, entity_id)
        
        if variant:
            new_assignment = ExperimentAssignmentModel(
                experiment_id=experiment.id,
                variant_id=variant.id,
                entity_id=entity_id
            )
            session.add(new_assignment)
            # Commit handled by caller usually, but assignment needs to be sticky
            # session.commit() 
            return variant
            
        return None

    def _assign_variant_logic(self, experiment: ABExperimentModel, entity_id: str) -> Optional[ABVariantModel]:
        """
        Determines which variant to assign based on weights.
        """
        variants = experiment.variants
        if not variants:
            return None
            
        total_weight = sum(v.weight for v in variants)
        if total_weight == 0:
            return variants[0] # Fallback
            
        # Deterministic assignment
        hash_input = f"{experiment.id}:{entity_id}".encode("utf-8")
        hash_val = int(hashlib.sha256(hash_input).hexdigest(), 16)
        
        # Normalize to 0..total_weight
        point = hash_val % total_weight
        
        current = 0
        for v in variants:
            current += v.weight
            if point < current:
                return v
                
        return variants[-1]
