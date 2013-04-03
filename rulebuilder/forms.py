from django import forms
from django.utils.translation import ugettext_lazy as _

from djangojsonschema.forms import JSONSchemaField
from djangojsonschema.jsonschema import DjangoFormToJSONSchema


#CONSIDER we may want varying languages
LANGUAGES = {}
LANGUAGE_SCHEMAS = {}

def register_condition(condition_cls, name, language_name):
    if language_name not in LANGUAGES:
        LANGUAGES[language_name] = dict()
    language = LANGUAGES[language_name]
    language[name] = condition_cls
    
    #clear cache
    LANGUAGE_SCHEMAS.pop(language_name, None)

def get_schema(language_name):
    if language_name not in LANGUAGE_SCHEMAS:
        form_translator = DjangoFormToJSONSchema()
        language = LANGUAGES[language_name]
        schema = {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "description": "Language schema for %s" % language_name,
            "definitions": {
                "basecondition": {
                    "type": "object",
                },
                "conditionArray": {
                    "type": "array",
                    "minItems": 1,
                    #CONSIDER: perhaps we want to enum the available implementing conditions
                    "items": {"$ref": "#/definitions/basecondition"},
                },
            },
            "properties": {
                "conditions": {
                    {"$ref": "#/definitions/conditionArray"}
                },
            },
        }
        
        for name, condition_cls in language.iteritems():
            definition = form_translator.convert_form(condition_cls)
            definition['extends'] = '#/definitions/basecondition'
            definition['condition_type'] = {"enum": [name]}
            schema['definitions'][name] = definition
        ifcondition = get_ifcondition_for_language(language, schema)
        definition = form_translator.convert_form(ifcondition)
        definition['extends'] = '#/definitions/basecondition'
        definition['condition_type'] = {"enum": ['ifcondition']}
        schema['definitions']['ifcondition'] = definition
        language['ifcondition'] = ifcondition
        LANGUAGE_SCHEMAS[language_name] = schema
    return LANGUAGE_SCHEMAS[language_name]

class Condition(forms.Form):
    def evaluate(self, context, node):
        return True

class BaseIfCondition(Condition):
    representation_string = _(u'If %(concatenation)s are %(evaluation)s of the following:')

    concatenation = forms.ChoiceField(choices=[('ALL', _('ALL')), 
                                               ('ANY', _('ANY')),
                                               ('NONE', _('NONE'))])
    evaluation = forms.ChoiceField(choices=[('TRUE', _('TRUE')),
                                            ('FALSE', _('FALSE'))])
    
    _available_conditions = {}
    
    def evaluate(self, context, node):
        if not len(node['conditions']): #Empty conditions always evaluate to true
            return True
        concat = node['concatenation']
        evaluation = node['evaluation']
        if concat == 'NONE':
            concat = 'ALL'
            if 'TRUE' == evaluation:
                evaluation = 'FALSE'
            else:
                evaluation = 'TRUE'
        if concat == 'ANY':
            for result in self._iterate(context, node):
                if str(result).upper() == evaluation:
                    return True
            return False
        assert concat == 'ALL'
        for result in self._iterate(context, node):
            if str(result).upper() != evaluation:
                return False
        return True
                
    def _iterate(self, context, node):
        for subcondition in node['conditions']:
            try:
                condition_cls = self._available_conditions[subcondition['condition_type']]
            except KeyError:
                pass
            else:
                condition = condition_cls()
                yield condition.evaluate(context, subcondition)

def get_ifcondition_for_language(available_conditions, language):
    class IfCondition(BaseIfCondition):
        _available_conditions = available_conditions
        #CONSIDER: this is to be a list of variable type conditions available from the schema language
        conditions = JSONSchemaField(schema=language)
    return IfCondition
