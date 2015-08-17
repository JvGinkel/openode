# -*- coding: utf-8 -*-
"""
    Inspired by http://www.wellfireinteractive.com/blog/custom-haystack-elasticsearch-backend/
"""

from haystack.backends.elasticsearch_backend import ElasticsearchSearchBackend, ElasticsearchSearchEngine

# from django.conf import settings
# STOP_WORDS_PATH = "/tmp/stop.txt"

ELASTICSEARCH_INDEX_SETTINGS = {
    'settings': {
        "analysis": {

            "analyzer": {
                "default": {
                    "type": "custom",
                    "tokenizer": "whitespace",
                    "filter": [
                        "asciifolding",
                        "standard",
                        "lowercase",
                        "haystack_edgengram",
                    ]
                },
                # "ngram_analyzer": {
                #     "type": "custom",
                #     "tokenizer": "lowercase",
                #     "filter": [
                #         "asciifolding",
                #         "haystack_ngram"
                #     ]
                # },
                # "edgengram_analyzer": {
                #     "type": "custom",
                #     "tokenizer": "lowercase",
                #     "filter": [
                #         "asciifolding",
                #         "haystack_edgengram"
                #     ]
                # }
            },

            "tokenizer": {
                "haystack_ngram_tokenizer": {
                    "type": "nGram",
                    "min_gram": 2,
                    "max_gram": 30,
                },
                "haystack_edgengram_tokenizer": {
                    "type": "edgeNGram",
                    "min_gram": 2,
                    "max_gram": 30,
                    "side": "front"
                }
            },

            "filter": {
                # "phonetic": {
                #     "type": "phonetic",
                #     "encoder": "metaphone"
                # },
                "haystack_ngram": {
                    "type": "nGram",
                    "min_gram": 2,
                    "max_gram": 30
                },
                "haystack_edgengram": {
                    "type": "edgeNGram",
                    "min_gram": 2,
                    "max_gram": 30
                },
            }

        }
    }
}


class ConfigurableElasticBackend(ElasticsearchSearchBackend):

    DEFAULT_ANALYZER = "default"

    def __init__(self, connection_alias, **connection_options):
        super(ConfigurableElasticBackend, self).__init__(
            connection_alias,
            **connection_options
            )
        setattr(self, 'DEFAULT_SETTINGS', ELASTICSEARCH_INDEX_SETTINGS)

    def build_schema(self, fields):
        content_field_name, mapping = super(ConfigurableElasticBackend, self).build_schema(fields)

        for field_name, field_class in fields.items():
            field_mapping = mapping[field_class.index_fieldname]

            if field_mapping['type'] == 'string' and field_class.indexed:
                if not hasattr(field_class, 'facet_for') and not field_class.field_type in('ngram', 'edge_ngram'):
                    field_mapping['analyzer'] = getattr(field_class, 'analyzer', self.DEFAULT_ANALYZER)
            mapping.update({field_class.index_fieldname: field_mapping})
        return (content_field_name, mapping)


class ConfigurableElasticSearchEngine(ElasticsearchSearchEngine):
    backend = ConfigurableElasticBackend
