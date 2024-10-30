"""Unit tests for rbtools.config.config.

Version Added:
    5.0
"""

from __future__ import annotations

from typing import Any, Optional

from rbtools.config.config import ConfigData
from rbtools.testing import TestCase


class MyConfigSubData(ConfigData):
    """Test cass for sub-keys within a config."""

    SUB_STR_KEY: str = 'sub-value'
    SUB_DICT_KEY: dict[str, Any] = {
        'subkey1': 'value1',
        'subkey2': {
            'subkey2.1': 'value2',
            'subkey2.2': 'value3',
        },
    }


class MyConfigData(ConfigData):
    """Test class for an example config."""

    INT_KEY: int = 123
    BOOL_KEY: bool = True
    STR_KEY: str = 'value'
    OPT_STR_KEY: Optional[str] = None
    LIST_KEY: list[Any] = [
        1,
        2,
        3,
        [4, 5],
        {
            '6': '6!',
        },
    ]
    DICT_KEY: dict[str, Any] = {
        'key1': 'value1',
        'key2': ['value2'],
        'key3': {
            'key3.1': 'value3',
            'key3.2': 'value4',
        },
    }
    SUB_KEYS: MyConfigSubData = MyConfigSubData()


class ConfigDataTests(TestCase):
    """Unit tests for ConfigData.

    Version Added:
        5.0
    """

    def test_with_defaults(self) -> None:
        """Testing ConfigData with defaults"""
        config = MyConfigData()

        self.assertEqual(config._raw_config, {})
        self.assertEqual(config.INT_KEY, 123)
        self.assertEqual(config.STR_KEY, 'value')
        self.assertEqual(config.LIST_KEY, [
            1,
            2,
            3,
            [4, 5],
            {
                '6': '6!',
            },
        ])
        self.assertEqual(config.DICT_KEY, {
            'key1': 'value1',
            'key2': ['value2'],
            'key3': {
                'key3.1': 'value3',
                'key3.2': 'value4',
            },
        })
        self.assertIs(config.BOOL_KEY, True)
        self.assertIsNone(config.OPT_STR_KEY)

        self.assertIsInstance(config.SUB_KEYS, MyConfigSubData)
        self.assertEqual(config.SUB_KEYS._raw_config, {})
        self.assertEqual(config.SUB_KEYS.SUB_STR_KEY, 'sub-value')
        self.assertEqual(config.SUB_KEYS.SUB_DICT_KEY, {
            'subkey1': 'value1',
            'subkey2': {
                'subkey2.1': 'value2',
                'subkey2.2': 'value3',
            },
        })

    def test_with_loaded(self) -> None:
        """Testing ConfigData with loaded values"""
        config = MyConfigData(config_dict={
            'BOOL_KEY': False,
            'DICT_KEY': {
                'a': 'z',
                'b': 'y',
                'c': 'x',
            },
            'INT_KEY': 456,
            'LIST_KEY': [99, 98, 97],
            'OPT_STR_KEY': 'not none',
            'STR_KEY': 'another value',
            'SUB_KEYS': {
                'SUB_STR_KEY': 'hi',
                'SUB_DICT_KEY': {
                    'A': 'B',
                    'C': 'D',
                },
            },
        })

        self.assertEqual(config._raw_config, {
            'BOOL_KEY': False,
            'DICT_KEY': {
                'a': 'z',
                'b': 'y',
                'c': 'x',
            },
            'INT_KEY': 456,
            'LIST_KEY': [99, 98, 97],
            'OPT_STR_KEY': 'not none',
            'STR_KEY': 'another value',
            'SUB_KEYS': {
                'SUB_STR_KEY': 'hi',
                'SUB_DICT_KEY': {
                    'A': 'B',
                    'C': 'D',
                },
            },
        })
        self.assertEqual(config.INT_KEY, 456)
        self.assertEqual(config.STR_KEY, 'another value')
        self.assertEqual(config.LIST_KEY, [99, 98, 97])
        self.assertEqual(config.DICT_KEY, {
            'a': 'z',
            'b': 'y',
            'c': 'x',
        })
        self.assertEqual(config.OPT_STR_KEY, 'not none')
        self.assertIs(config.BOOL_KEY, False)

        self.assertIsInstance(config.SUB_KEYS, MyConfigSubData)
        self.assertEqual(config.SUB_KEYS._raw_config, {
            'SUB_STR_KEY': 'hi',
            'SUB_DICT_KEY': {
                'A': 'B',
                'C': 'D',
            },
        })
        self.assertEqual(config.SUB_KEYS.SUB_STR_KEY, 'hi')
        self.assertEqual(config.SUB_KEYS.SUB_DICT_KEY, {
            'A': 'B',
            'C': 'D',
        })

        self.assertIsNot(config.SUB_KEYS, MyConfigData.SUB_KEYS)

    def test_contains(self) -> None:
        """Testing ConfigData.__contains__"""
        config = MyConfigData(config_dict={
            'CUSTOM': 'value',
        })

        # We're using assertTrue(... in ...) instead of assertIn() because
        # the latter is typed wrong for __contains__.
        self.assertTrue('INT_KEY' in config)
        self.assertTrue('CUSTOM' in config)

    def test_copy(self) -> None:
        """Testing ConfigData.copy"""
        config1 = MyConfigData()
        config2 = config1.copy()

        self.assertEqual(config1, config2)
        self.assertIsNot(config1, config2)
        self.assertIsNot(config1._raw_config, config2._raw_config)
        self.assertIsNot(config1.DICT_KEY, config2.DICT_KEY)
        self.assertIsNot(config1.DICT_KEY['key2'], config2.DICT_KEY['key2'])
        self.assertIsNot(config1.DICT_KEY['key3'], config2.DICT_KEY['key3'])
        self.assertIsNot(config1.LIST_KEY, config2.LIST_KEY)
        self.assertIsNot(config1.SUB_KEYS, config2.SUB_KEYS)
        self.assertIsNot(config1.SUB_KEYS._raw_config,
                         config2.SUB_KEYS._raw_config)

        for item1, item2 in zip(config1.LIST_KEY, config2.LIST_KEY):
            if isinstance(item1, (list, dict)):
                self.assertIsNot(item1, item2)

    def test_get(self) -> None:
        """Testing ConfigData.get"""
        config = MyConfigData(config_dict={
            'INT_KEY': 456,
        })

        self.assertEqual(config.get('INT_KEY'), 456)

    def test_get_with_class_default(self) -> None:
        """Testing ConfigData.get with class-provided default"""
        config = MyConfigData()

        self.assertEqual(config.get('INT_KEY'), 123)

    def test_get_with_caller_default(self) -> None:
        """Testing ConfigData.get with caller-provided default"""
        config = MyConfigData()

        self.assertEqual(config.get('FOO', 'bar'), 'bar')

    def test_get_with_no_value(self) -> None:
        """Testing ConfigData.get with no value stored and no default"""
        config = MyConfigData()

        self.assertIsNone(config.get('FOO'))

    def test_getattr(self) -> None:
        """Testing ConfigData.__getattribute__"""
        config = MyConfigData(config_dict={
            'INT_KEY': 456,
        })

        self.assertEqual(config.INT_KEY, 456)

    def test_getattr_with_class_default(self) -> None:
        """Testing ConfigData.__getattribute__ with class-provided default"""
        config = MyConfigData()

        self.assertEqual(config.INT_KEY, 123)

    def test_getattr_with_no_value(self) -> None:
        """Testing ConfigData.__getattribute__ with no value stored and no
        default
        """
        config = MyConfigData()

        with self.assertRaises(AttributeError):
            self.assertIsNone(config.FOO)

    def test_getitem(self) -> None:
        """Testing ConfigData.__getitem__"""
        config = MyConfigData(config_dict={
            'INT_KEY': 456,
        })

        self.assertEqual(config['INT_KEY'], 456)

    def test_getitem_with_class_default(self) -> None:
        """Testing ConfigData.__getitem__ with class-provided default"""
        config = MyConfigData()

        self.assertEqual(config['INT_KEY'], 123)

    def test_getitem_with_no_value(self) -> None:
        """Testing ConfigData.__getitem__ with no value stored and no
        default
        """
        config = MyConfigData()

        with self.assertRaises(KeyError):
            self.assertIsNone(config['FOO'])

    def test_merge(self) -> None:
        """Testing ConfigData.merge"""
        config1 = MyConfigData(config_dict={
            'BOOL_KEY': False,
            'DICT_KEY': {
                'a': 'z',
                'b': 'y',
                'c': 'x',
            },
            'INT_KEY': 456,
            'LIST_KEY': [99, 98, 97],
            'OPT_STR_KEY': 'not none',
            'STR_KEY': 'another value',
            'SUB_KEYS': {
                'SUB_STR_KEY': 'hi',
                'SUB_DICT_KEY': {
                    'A': 'B',
                    'C': 'D',
                },
            },
        })

        config2 = MyConfigData(config_dict={
            'BOOL_KEY': True,
            'DICT_KEY': {
                'd': 'w',
                'e': 'v',
            },
            'LIST_KEY': [100, 200, 300],
            'SUB_KEYS': {
                'SUB_DICT_KEY': {
                    'W': 'X',
                    'Y': 'Z',
                },
            },
        })

        config1.merge(config2)

        self.assertEqual(config1._raw_config, {
            'BOOL_KEY': True,
            'DICT_KEY': {
                'a': 'z',
                'b': 'y',
                'c': 'x',
                'd': 'w',
                'e': 'v',
            },
            'INT_KEY': 456,
            'LIST_KEY': [100, 200, 300],
            'OPT_STR_KEY': 'not none',
            'STR_KEY': 'another value',
            'SUB_KEYS': {
                'SUB_STR_KEY': 'hi',
                'SUB_DICT_KEY': {
                    'A': 'B',
                    'C': 'D',
                    'W': 'X',
                    'Y': 'Z',
                },
            },
        })
