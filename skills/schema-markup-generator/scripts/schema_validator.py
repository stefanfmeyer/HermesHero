#!/usr/bin/env python3
"""
schema_validator.py
Validates generated JSON-LD schema against schema.org rules and Google Rich Results requirements.
"""
import sys, json, re
from collections import defaultdict

# Schema.org type definitions (required/optional properties)
# Based on https://schema.org/docs/full.html
SCHEMA_TYPES = {
    'FAQPage': {
        'required': ['mainEntity'],
        'optional': ['@context', '@type', 'name', 'description'],
        'nested_types': {
            'mainEntity': 'Question'
        },
        'google_min': {'mainEntity': 1},  # Google Rich Results requirement
        'description': 'A page with frequently asked questions'
    },
    'Question': {
        'required': ['name', 'acceptedAnswer'],
        'optional': ['@type', 'text', 'answerCount', 'author'],
        'nested_types': {
            'acceptedAnswer': 'Answer'
        },
        'description': 'A specific question that can be posted on a Q&A site'
    },
    'Answer': {
        'required': ['text'],
        'optional': ['@type', 'dateCreated', 'author', 'upvoteCount'],
        'description': 'An answer to a question'
    },
    'FinancialProduct': {
        'required': ['name'],
        'optional': ['@context', '@type', 'description', 'interestRate', 'loanType', 
                     'annualPercentageRate', 'provider', 'offers', 'url'],
        'enums': {
            'loanType': ['PersonalLoan', 'BusinessLoan', 'MortgageLoan', 'StudentLoan', 
                        'PaydayLoan', 'RefinanceLoan', 'SecuredLoan', 'UnsecuredLoan']
        },
        'description': 'A financial product or service'
    },
    'Organization': {
        'required': ['name'],
        'optional': ['@context', '@type', 'url', 'logo', 'description', 'sameAs', 
                     'contactPoint', 'address', 'telephone'],
        'description': 'An organization such as a company or institution'
    },
    'BreadcrumbList': {
        'required': ['itemListElement'],
        'optional': ['@context', '@type'],
        'nested_types': {
            'itemListElement': 'ListItem'
        },
        'google_min': {'itemListElement': 2},  # Google requires at least 2 items
        'description': 'A list of breadcrumbs'
    },
    'ListItem': {
        'required': ['position', 'name'],
        'optional': ['@type', 'item', 'nextItem', 'previousItem'],
        'description': 'A list item, e.g. of a breadcrumb list'
    },
    'HowTo': {
        'required': ['name'],
        'optional': ['@context', '@type', 'description', 'step', 'image', 'timeRequired', 
                     'supply', 'tool', 'yield'],
        'nested_types': {
            'step': 'HowToStep'
        },
        'google_min': {'step': 1},
        'description': 'Instructions on how to perform a task'
    },
    'HowToStep': {
        'required': ['text'],
        'optional': ['@type', 'name', 'image', 'position'],
        'description': 'A step in the instructions for how to achieve a result'
    },
    'VideoObject': {
        'required': ['name'],
        'optional': ['@context', '@type', 'description', 'embedUrl', 'contentUrl', 
                     'uploadDate', 'duration', 'thumbnailUrl'],
        'google_required_for_rich': ['name', 'description', 'thumbnailUrl', 'uploadDate'],
        'description': 'A video object'
    },
    'Dataset': {
        'required': ['name'],
        'optional': ['@context', '@type', 'description', 'variableMeasured', 'url', 
                     'creator', 'license', 'distribution'],
        'description': 'A body of structured information describing some topic'
    },
    'Service': {
        'required': ['name'],
        'optional': ['@context', '@type', 'description', 'provider', 'areaServed', 
                     'hasOfferCatalog', 'offers'],
        'description': 'A service provided by an organization'
    },
    'CollectionPage': {
        'required': ['name'],
        'optional': ['@context', '@type', 'description', 'url'],
        'description': 'A web page that displays a collection of items'
    },
    'ItemList': {
        'required': ['itemListElement'],
        'optional': ['@context', '@type', 'numberOfItems'],
        'description': 'A list of items'
    },
    'Product': {
        'required': ['name'],
        'optional': ['@context', '@type', 'description', 'image', 'offers', 'brand', 
                     'sku', 'aggregateRating'],
        'google_required_for_rich': ['name', 'offers'],
        'description': 'A product'
    },
    'Offer': {
        'required': ['price', 'priceCurrency'],
        'optional': ['@type', 'availability', 'url', 'seller'],
        'enums': {
            'availability': ['InStock', 'OutOfStock', 'PreOrder', 'SoldOut']
        },
        'description': 'An offer to sell an item'
    },
    'Article': {
        'required': ['headline'],
        'optional': ['@context', '@type', 'description', 'image', 'author', 
                     'datePublished', 'dateModified'],
        'google_required_for_rich': ['headline', 'image', 'datePublished'],
        'description': 'An article'
    }
}

# Property type validation
PROPERTY_TYPES = {
    'name': 'Text',
    'description': 'Text',
    'url': 'URL',
    'image': 'ImageObject or URL',
    'price': 'Number or Text',
    'priceCurrency': 'Text',
    'interestRate': 'Number or QuantitativeValue',
    'annualPercentageRate': 'Number or QuantitativeValue',
    'position': 'Integer or Text',
    'text': 'Text',
    'embedUrl': 'URL',
    'contentUrl': 'URL',
    'thumbnailUrl': 'URL',
    'uploadDate': 'Date',
    'duration': 'Duration',
    'telephone': 'Text',
    'email': 'Email',
    'sameAs': 'URL',
    'logo': 'ImageObject or URL',
}

# URL pattern
URL_PATTERN = re.compile(r'^https?://[^\s]+$')
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')


class SchemaValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
    
    def validate(self, schema_data):
        """Validate a complete JSON-LD schema."""
        self.errors = []
        self.warnings = []
        self.info = []
        
        if not schema_data:
            self.errors.append("Empty schema data")
            return self.get_report()
        
        # Handle @graph or single entity
        if '@graph' in schema_data:
            entities = schema_data['@graph']
        else:
            entities = [schema_data]
        
        for i, entity in enumerate(entities):
            self.validate_entity(entity, f"Entity {i+1}")
        
        return self.get_report()
    
    def validate_entity(self, entity, path):
        """Validate a single schema entity."""
        if not isinstance(entity, dict):
            self.errors.append(f"{path}: Entity must be an object")
            return
        
        entity_type = entity.get('@type')
        if not entity_type:
            self.errors.append(f"{path}: Missing @type")
            return
        
        # Check if type is known
        if entity_type not in SCHEMA_TYPES:
            self.warnings.append(f"{path}: Unknown type '{entity_type}' (may still be valid)")
            return
        
        type_def = SCHEMA_TYPES[entity_type]
        
        # Check required properties
        for req_prop in type_def.get('required', []):
            if req_prop not in entity:
                self.errors.append(f"{path} ({entity_type}): Missing required property '{req_prop}'")
        
        # Check Google Rich Results minimum requirements
        google_reqs = type_def.get('google_required_for_rich', [])
        for req_prop in google_reqs:
            if req_prop not in entity:
                self.warnings.append(f"{path} ({entity_type}): Google Rich Results requires '{req_prop}'")
        
        # Check Google minimum counts
        for prop, min_count in type_def.get('google_min', {}).items():
            if prop in entity:
                value = entity[prop]
                actual_count = len(value) if isinstance(value, list) else 1
                if actual_count < min_count:
                    self.warnings.append(f"{path} ({entity_type}): Google requires at least {min_count} {prop} (found {actual_count})")
        
        # Validate property types
        for prop, value in entity.items():
            if prop.startswith('@'):
                continue
            
            # Check if property is known for this type
            all_props = type_def.get('required', []) + type_def.get('optional', [])
            if prop not in all_props and prop not in ['@context', '@type']:
                self.info.append(f"{path} ({entity_type}): Property '{prop}' not in standard definition")
            
            # Validate property value type
            self.validate_property_type(value, prop, f"{path}.{prop}")
            
            # Validate enumerated values
            if prop in type_def.get('enums', {}):
                allowed = type_def['enums'][prop]
                if isinstance(value, str) and value not in allowed:
                    self.warnings.append(f"{path}.{prop}: Value '{value}' should be one of {allowed}")
            
            # Validate nested types
            if prop in type_def.get('nested_types', {}):
                nested_type = type_def['nested_types'][prop]
                if isinstance(value, list):
                    for i, item in enumerate(value):
                        self.validate_nested_type(item, nested_type, f"{path}.{prop}[{i}]")
                else:
                    self.validate_nested_type(value, nested_type, f"{path}.{prop}")
    
    def validate_property_type(self, value, prop, path):
        """Validate property value type."""
        if prop not in PROPERTY_TYPES:
            return
        
        expected_type = PROPERTY_TYPES[prop]
        
        if expected_type == 'URL':
            if isinstance(value, str) and not URL_PATTERN.match(value):
                self.warnings.append(f"{path}: Should be a valid URL")
        
        elif expected_type == 'Email':
            if isinstance(value, str) and not EMAIL_PATTERN.match(value):
                self.warnings.append(f"{path}: Should be a valid email")
        
        elif expected_type == 'Date':
            if isinstance(value, str) and not DATE_PATTERN.match(value):
                self.warnings.append(f"{path}: Should be in YYYY-MM-DD format")
        
        elif expected_type == 'Number':
            if not isinstance(value, (int, float)):
                self.warnings.append(f"{path}: Should be a number")
        
        elif expected_type == 'Text':
            if not isinstance(value, str):
                self.warnings.append(f"{path}: Should be text")
    
    def validate_nested_type(self, item, expected_type, path):
        """Validate nested entity type."""
        if not isinstance(item, dict):
            self.warnings.append(f"{path}: Should be {expected_type} object")
            return
        
        item_type = item.get('@type')
        if item_type and item_type != expected_type:
            self.warnings.append(f"{path}: Expected {expected_type}, got {item_type}")
        
        # Recursively validate
        if expected_type in SCHEMA_TYPES:
            self.validate_entity(item, path)
    
    def get_report(self):
        """Generate validation report."""
        return {
            'valid': len(self.errors) == 0,
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info,
            'summary': {
                'errors': len(self.errors),
                'warnings': len(self.warnings),
                'info': len(self.info)
            }
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: schema_validator.py <schema.json>")
        sys.exit(1)
    
    schema_file = sys.argv[1]
    
    try:
        with open(schema_file, 'r') as f:
            schema_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {schema_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}")
        sys.exit(1)
    
    validator = SchemaValidator()
    report = validator.validate(schema_data)
    
    # Print report
    print("=" * 60)
    print("SCHEMA VALIDATION REPORT")
    print("=" * 60)
    print(f"\nStatus: {'✅ VALID' if report['valid'] else '❌ INVALID'}")
    print(f"Errors: {report['summary']['errors']}")
    print(f"Warnings: {report['summary']['warnings']}")
    print(f"Info: {report['summary']['info']}")
    
    if report['errors']:
        print("\n--- ERRORS ---")
        for error in report['errors']:
            print(f"  ❌ {error}")
    
    if report['warnings']:
        print("\n--- WARNINGS ---")
        for warning in report['warnings']:
            print(f"  ⚠️  {warning}")
        
        # Add fix suggestions for common warnings
        if any('Google Rich Results' in w and 'thumbnailUrl' in w for w in report['warnings']):
            print("\n💡 SUGGESTION: Add thumbnailUrl to VideoObject (e.g., YouTube thumbnail: https://img.youtube.com/vi/VIDEO_ID/maxresdefault.jpg)")
        
        if any('Google Rich Results' in w and 'uploadDate' in w for w in report['warnings']):
            print("💡 SUGGESTION: Add uploadDate to VideoObject in YYYY-MM-DD format")
    
    if report['info']:
        print("\n--- INFO ---")
        for info in report['info']:
            print(f"  ℹ️  {info}")
    
    print("\n" + "=" * 60)
    
    # Exit with error code if validation failed
    sys.exit(0 if report['valid'] else 1)


if __name__ == '__main__':
    main()
