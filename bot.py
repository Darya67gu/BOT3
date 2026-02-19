"""
Telegram бот - Тренажер по программированию
Версия: 1.5
Библиотека: aiogram 3.25.0
"""

# ========== ИМПОРТЫ ==========
import logging
import sqlite3
from datetime import datetime
import asyncio
import ast
import sys
import io
import contextlib
import traceback
import re
import os
import json
import time
import random
import math
import subprocess
import tempfile
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
from collections import defaultdict
import shutil

# Импорты из aiogram
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    Message, CallbackQuery
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== МОДУЛЬ ПРОВЕРКИ КОДА ==========
class CodeChecker:
    """Класс для проверки кода на разных языках"""
    
    @staticmethod
    def check_python(code: str, function_name: str = None, test_cases: List[Dict] = None) -> Dict[str, Any]:
        """Проверка Python кода"""
        try:
            # Проверка синтаксиса
            ast.parse(code)
            
            if not function_name or not test_cases:
                return {
                    'valid': True,
                    'language': 'python',
                    'message': '✅ Синтаксис верный'
                }
            
            # Проверка семантики с тестами
            local_namespace = {}
            stdout_capture = io.StringIO()
            
            with contextlib.redirect_stdout(stdout_capture):
                exec(code, {'__builtins__': __builtins__}, local_namespace)
            
            if function_name not in local_namespace:
                return {
                    'passed': False,
                    'error': f'Функция {function_name} не определена',
                    'test_results': [],
                    'passed_count': 0,
                    'total_count': len(test_cases)
                }
            
            user_function = local_namespace[function_name]
            test_results = []
            passed_count = 0
            
            for i, test in enumerate(test_cases, 1):
                try:
                    args = test['input']
                    expected = test['expected']
                    result = user_function(*args)
                    passed = (result == expected)
                    
                    if passed:
                        passed_count += 1
                    
                    test_results.append({
                        'test_id': i,
                        'input': args,
                        'expected': expected,
                        'actual': result,
                        'passed': passed,
                        'error': None
                    })
                    
                except Exception as e:
                    test_results.append({
                        'test_id': i,
                        'input': test['input'],
                        'expected': test['expected'],
                        'actual': None,
                        'passed': False,
                        'error': str(e)
                    })
            
            return {
                'passed': passed_count == len(test_cases),
                'test_results': test_results,
                'passed_count': passed_count,
                'total_count': len(test_cases),
                'output': stdout_capture.getvalue()
            }
            
        except SyntaxError as e:
            return {
                'valid': False,
                'error': str(e),
                'line': e.lineno,
                'message': f'❌ Ошибка в строке {e.lineno}: {e.msg}'
            }
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'message': f'❌ Ошибка: {str(e)}'
            }
    
    @staticmethod
    def check_javascript(code: str, function_name: str = None, test_cases: List[Dict] = None) -> Dict[str, Any]:
        """Проверка JavaScript кода с использованием Node.js"""
        try:
            # Проверка базового синтаксиса
            if 'function' not in code and '=>' not in code:
                return {
                    'valid': False,
                    'error': 'Код должен содержать функцию',
                    'message': '❌ Код не содержит объявления функции'
                }
            
            if not function_name or not test_cases:
                return {
                    'valid': True,
                    'language': 'javascript',
                    'message': '✅ Синтаксис корректен (базовая проверка)'
                }
            
            # Создаем временный файл с кодом и тестами
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
                # Формируем код с тестами
                test_code = code + '\n\n'
                test_code += '// Тесты\n'
                test_code += 'const tests = ' + json.dumps(test_cases) + ';\n\n'
                test_code += 'let passed = 0;\n'
                test_code += 'const results = [];\n\n'
                test_code += 'for (let i = 0; i < tests.length; i++) {\n'
                test_code += '    try {\n'
                test_code += '        const test = tests[i];\n'
                test_code += f'        const result = {function_name}(...test.input);\n'
                test_code += '        const expected = test.expected;\n'
                test_code += '        const success = JSON.stringify(result) === JSON.stringify(expected);\n'
                test_code += '        if (success) passed++;\n'
                test_code += '        results.push({\n'
                test_code += '            test_id: i+1,\n'
                test_code += '            input: test.input,\n'
                test_code += '            expected: expected,\n'
                test_code += '            actual: result,\n'
                test_code += '            passed: success,\n'
                test_code += '            error: null\n'
                test_code += '        });\n'
                test_code += '    } catch (e) {\n'
                test_code += '        results.push({\n'
                test_code += '            test_id: i+1,\n'
                test_code += '            input: tests[i].input,\n'
                test_code += '            expected: tests[i].expected,\n'
                test_code += '            actual: null,\n'
                test_code += '            passed: false,\n'
                test_code += '            error: e.toString()\n'
                test_code += '        });\n'
                test_code += '    }\n'
                test_code += '}\n\n'
                test_code += 'console.log(JSON.stringify({ passed: passed === tests.length, results: results, passed_count: passed, total_count: tests.length }));\n'
                
                f.write(test_code)
                temp_file = f.name
            
            # Запускаем Node.js для выполнения кода
            try:
                result = subprocess.run(['node', temp_file], 
                                       capture_output=True, 
                                       text=True, 
                                       timeout=5,
                                       encoding='utf-8')
                
                os.unlink(temp_file)  # Удаляем временный файл
                
                if result.returncode != 0:
                    return {
                        'passed': False,
                        'error': f'Ошибка выполнения: {result.stderr}',
                        'passed_count': 0,
                        'total_count': len(test_cases)
                    }
                
                # Парсим результат
                output = result.stdout.strip()
                # Ищем JSON в выводе
                import re
                json_match = re.search(r'\{.*\}', output, re.DOTALL)
                if json_match:
                    test_result = json.loads(json_match.group())
                    return test_result
                else:
                    return {
                        'passed': False,
                        'error': 'Не удалось распарсить результат',
                        'output': output,
                        'passed_count': 0,
                        'total_count': len(test_cases)
                    }
                    
            except subprocess.TimeoutExpired:
                os.unlink(temp_file)
                return {
                    'passed': False,
                    'error': 'Превышено время выполнения (5 сек)',
                    'passed_count': 0,
                    'total_count': len(test_cases)
                }
            except FileNotFoundError:
                return {
                    'passed': False,
                    'error': 'Node.js не установлен на сервере',
                    'message': '❌ Для проверки JavaScript требуется Node.js',
                    'passed_count': 0,
                    'total_count': len(test_cases)
                }
                
        except Exception as e:
            return {
                'passed': False,
                'error': str(e),
                'passed_count': 0,
                'total_count': len(test_cases) if test_cases else 0
            }
    
    @staticmethod
    def check_java(code: str, function_name: str = None, test_cases: List[Dict] = None) -> Dict[str, Any]:
        """Проверка Java кода"""
        try:
            # Базовая проверка наличия класса
            if 'class' not in code:
                return {
                    'valid': False,
                    'error': 'Код должен содержать класс',
                    'message': '❌ Код не содержит объявления класса'
                }
            
            # Извлекаем имя класса из кода
            import re
            class_match = re.search(r'(?:public\s+)?class\s+(\w+)', code)
            if not class_match:
                return {
                    'valid': False,
                    'error': 'Не удалось определить имя класса',
                    'message': '❌ Не удалось определить имя класса'
                }
            
            class_name = class_match.group(1)
            
            # Определяем, является ли класс public
            is_public = 'public class' in code
            
            # Создаем временный файл с правильным именем
            if is_public:
                # Для public класса имя файла должно совпадать с именем класса
                temp_dir = tempfile.gettempdir()
                temp_file = os.path.join(temp_dir, f"{class_name}.java")
                
                # Удаляем старый файл, если существует
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(code)
            else:
                # Для non-public класса можно использовать любое имя
                with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False, encoding='utf-8') as f:
                    f.write(code)
                    temp_file = f.name
            
            # Если нет тестов, просто проверяем компиляцию
            if not function_name or not test_cases:
                try:
                    compile_result = subprocess.run(['javac', temp_file], 
                                                   capture_output=True, 
                                                   text=True, 
                                                   timeout=10,
                                                   encoding='utf-8')
                    
                    success = compile_result.returncode == 0
                    os.unlink(temp_file)
                    
                    if success:
                        return {
                            'valid': True,
                            'language': 'java',
                            'message': '✅ Компиляция успешна'
                        }
                    else:
                        return {
                            'valid': False,
                            'error': compile_result.stderr,
                            'message': '❌ Ошибка компиляции'
                        }
                        
                except FileNotFoundError:
                    return {
                        'valid': False,
                        'error': 'Java JDK не установлен',
                        'message': '❌ Для проверки Java требуется JDK'
                    }
            
            # Компилируем Java код
            try:
                compile_result = subprocess.run(['javac', temp_file], 
                                               capture_output=True, 
                                               text=True, 
                                               timeout=10,
                                               encoding='utf-8')
                
                if compile_result.returncode != 0:
                    os.unlink(temp_file)
                    return {
                        'passed': False,
                        'error': f'Ошибка компиляции: {compile_result.stderr}',
                        'passed_count': 0,
                        'total_count': len(test_cases)
                    }
                
                # Запускаем Java программу
                class_path = os.path.dirname(temp_file)
                
                run_result = subprocess.run(['java', '-cp', class_path, class_name],
                                           capture_output=True,
                                           text=True,
                                           timeout=5,
                                           encoding='utf-8')
                
                # Удаляем файлы
                os.unlink(temp_file)
                class_file = os.path.join(class_path, class_name + '.class')
                if os.path.exists(class_file):
                    os.unlink(class_file)
                
                if run_result.returncode != 0:
                    return {
                        'passed': False,
                        'error': f'Ошибка выполнения: {run_result.stderr}',
                        'passed_count': 0,
                        'total_count': len(test_cases)
                    }
                
                # Проверяем вывод программы
                output = run_result.stdout.strip()
                
                # Для задач с тестами
                if test_cases and len(test_cases) > 0:
                    test_results = []
                    passed_count = 0
                    
                    for i, test in enumerate(test_cases, 1):
                        expected = str(test['expected']).strip()
                        if expected in output:
                            passed_count += 1
                            test_results.append({
                                'test_id': i,
                                'input': test['input'],
                                'expected': expected,
                                'actual': output,
                                'passed': True,
                                'error': None
                            })
                        else:
                            test_results.append({
                                'test_id': i,
                                'input': test['input'],
                                'expected': expected,
                                'actual': output,
                                'passed': False,
                                'error': 'Вывод не соответствует ожидаемому'
                            })
                    
                    return {
                        'passed': passed_count == len(test_cases),
                        'test_results': test_results,
                        'passed_count': passed_count,
                        'total_count': len(test_cases),
                        'output': output
                    }
                
                return {
                    'passed': True,
                    'message': '✅ Код выполнен успешно',
                    'output': output
                }
                    
            except subprocess.TimeoutExpired:
                os.unlink(temp_file)
                return {
                    'passed': False,
                    'error': 'Превышено время выполнения (5 сек)',
                    'passed_count': 0,
                    'total_count': len(test_cases)
                }
            except FileNotFoundError:
                return {
                    'passed': False,
                    'error': 'Java JDK не установлен на сервере',
                    'message': '❌ Для проверки Java требуется JDK',
                    'passed_count': 0,
                    'total_count': len(test_cases)
                }
            except Exception as e:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                return {
                    'passed': False,
                    'error': str(e),
                    'passed_count': 0,
                    'total_count': len(test_cases)
                }
                
        except Exception as e:
            return {
                'passed': False,
                'error': str(e),
                'passed_count': 0,
                'total_count': len(test_cases) if test_cases else 0
            }
    
    @staticmethod
    def check_code(code: str, language: str, function_name: str = None, test_cases: List[Dict] = None) -> Dict[str, Any]:
        """Универсальная проверка кода на любом языке"""
        if language == 'python':
            return CodeChecker.check_python(code, function_name, test_cases)
        elif language == 'javascript':
            return CodeChecker.check_javascript(code, function_name, test_cases)
        elif language == 'java':
            return CodeChecker.check_java(code, function_name, test_cases)
        else:
            return {
                'valid': False,
                'error': f'Язык {language} не поддерживается',
                'message': f'❌ Проверка для {language} временно недоступна'
            }

# ========== ФУНКЦИИ ОПРЕДЕЛЕНИЯ ЯЗЫКА ==========
def detect_language(code: str) -> str:
    """
    Определяет язык программирования по коду
    """
    code = code.strip()
    
    # Признаки Java
    java_patterns = [
        r'public\s+class\s+\w+',
        r'public\s+static\s+void\s+main\s*\(',
        r'System\.out\.println',
        r'import\s+java\.',
        r'@Override',
        r'extends\s+\w+',
        r'implements\s+\w+',
        r'private\s+\w+\s+\w+\s*[=;]',
        r'protected\s+\w+\s+\w+\s*[=;]'
    ]
    
    # Признаки JavaScript
    js_patterns = [
        r'function\s+\w+\s*\(',
        r'const\s+\w+\s*=',
        r'let\s+\w+\s*=',
        r'var\s+\w+\s*=',
        r'console\.log\s*\(',
        r'document\.',
        r'window\.',
        r'=>\s*{',
        r'export\s+(default\s+)?\w+',
        r'import\s+.*\s+from\s+[\'"]',
        r'require\s*\([\'"]'
    ]
    
    # Признаки Python
    python_patterns = [
        r'def\s+\w+\s*\(',
        r'import\s+\w+',
        r'from\s+\w+\s+import',
        r'if\s+__name__\s*==\s*[\'"]__main__[\'"]',
        r'print\s*\(',
        r'class\s+\w+\s*:',
        r'elif\s+.+:',
        r'else\s*:',
        r'try\s*:',
        r'except\s+\w+\s*:',
        r'with\s+open\s*\(',
        r'lambda\s+\w+\s*:',
        r'@\w+'
    ]
    
    # Подсчитываем совпадения
    java_score = sum(1 for pattern in java_patterns if re.search(pattern, code, re.MULTILINE))
    js_score = sum(1 for pattern in js_patterns if re.search(pattern, code, re.MULTILINE))
    python_score = sum(1 for pattern in python_patterns if re.search(pattern, code, re.MULTILINE))
    
    # Особые случаи
    if 'public static void main' in code or 'System.out.println' in code:
        return 'java'
    if 'console.log' in code or ('function' in code and ('var' in code or 'let' in code or 'const' in code)):
        return 'javascript'
    if 'def ' in code and ':' in code or 'print(' in code:
        return 'python'
    
    # Возвращаем язык с наибольшим количеством совпадений
    scores = {'java': java_score, 'javascript': js_score, 'python': python_score}
    detected = max(scores, key=scores.get)
    
    # Если совсем нет совпадений, возвращаем 'unknown'
    if scores[detected] == 0:
        return 'unknown'
    
    return detected

def format_result_message(result: dict, language: str, task: dict) -> str:
    """Форматирует результат проверки"""
    
    if 'error' in result and result['error']:
        if 'Node.js' in result['error'] or 'JDK' in result['error']:
            return f"❌ *Ошибка:* {result['error']}"
        return f"❌ *Ошибка в коде:*\n```\n{result['error']}\n```"
    
    if result.get('passed', False):
        response = f"✅ *ВСЕ ТЕСТЫ ПРОЙДЕНЫ!*\n\n"
        response += f"🎉 Поздравляю! Ты правильно решил задачу на *{language.capitalize()}*!\n\n"
    elif result.get('valid', False):
        response = f"✅ *СИНТАКСИС ВЕРНЫЙ*\n\n"
        response += f"Код на *{language.capitalize()}* написан без синтаксических ошибок.\n\n"
    else:
        response = f"❌ *ТЕСТЫ НЕ ПРОЙДЕНЫ*\n\n"
        response += f"Пройдено тестов: {result.get('passed_count', 0)}/{result.get('total_count', len(task['test_cases']))}\n\n"
    
    # Показываем результаты тестов
    if 'test_results' in result and result['test_results']:
        response += "*Результаты тестов:*\n"
        for test in result['test_results']:
            if test.get('passed'):
                response += f"✅ Тест {test['test_id']}: {test['input']} → {test['actual']}\n"
            else:
                response += f"❌ Тест {test['test_id']}: {test['input']} → "
                if test.get('actual') is None:
                    response += f"Ошибка: {test.get('error', 'неизвестная ошибка')}\n"
                else:
                    response += f"получено {test['actual']}, ожидалось {test['expected']}\n"
    
    return response

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8533950306:AAFDADV8ksvHmw1e8ELqthKWs0Osoua91h8"

# ========== БАЗА ВОПРОСОВ ==========
QUESTIONS = {
    'python': [
        {
            'question': 'Как вывести текст в Python?', 
            'options': ['print("text")', 'console.log("text")', 'echo "text"', 'System.out.println("text")'], 
            'correct': 0
        },
        {
            'question': 'Как создать список в Python?', 
            'options': ['list = []', 'array = []', 'arr = []', 'list()'], 
            'correct': 0
        },
        {
            'question': 'Какая функция возвращает длину списка?', 
            'options': ['size()', 'length()', 'len()', 'count()'], 
            'correct': 2
        },
        {
            'question': 'Как объявить функцию в Python?', 
            'options': ['function myFunc():', 'def myFunc():', 'func myFunc():', 'define myFunc():'], 
            'correct': 1
        }
    ],
    
    'javascript': [
        {
            'question': 'Как вывести текст в JavaScript?', 
            'options': ['print("text")', 'console.log("text")', 'echo "text"', 'System.out.println("text")'], 
            'correct': 1
        },
        {
            'question': 'Как объявить переменную в JS?', 
            'options': ['var x;', 'let x;', 'const x;', 'Все варианты'], 
            'correct': 3
        },
        {
            'question': 'Как создать массив в JS?', 
            'options': ['[]', '{}', '()', '<>'], 
            'correct': 0
        },
        {
            'question': 'Как объявить функцию в JavaScript?',
            'options': ['function myFunc() {}', 'def myFunc() {}', 'func myFunc()', 'create function myFunc()'],
            'correct': 0
        }
    ],
    
    'java': [
        {
            'question': 'Как вывести текст в Java?', 
            'options': ['print("text")', 'console.log("text")', 'System.out.println("text")', 'echo "text"'], 
            'correct': 2
        },
        {
            'question': 'Что такое JVM?', 
            'options': ['Java Virtual Machine', 'Java Visual Model', 'Java Variable Memory', 'Java Version Manager'], 
            'correct': 0
        },
        {
            'question': 'Какое ключевое слово для наследования?', 
            'options': ['extends', 'implements', 'inherits', 'super'], 
            'correct': 0
        },
        {
            'question': 'Как объявить метод в Java?',
            'options': ['public void method() {}', 'function method() {}', 'def method() {}', 'method() {}'],
            'correct': 0
        }
    ]
}

# ========= ЗАДАНИЯ ПО КАТЕГОРИЯМ =========
TASKS = {
    'python': {
        'syntax': [
            {
                'id': 'py_syntax_print',
                'title': '📝 Синтаксис: Вывод текста',
                'difficulty': 'easy',
                'category': 'syntax',
                'description': 'Напишите программу, которая выводит на экран фразу "Hello, World!"',
                'function_name': None,
                'template': '# Напишите код здесь\nprint()',
                'test_cases': [
                    {'input': [], 'expected': 'Hello, World!\n', 'type': 'output'}
                ],
                'hint': 'Используйте функцию print()',
                'solution': 'print("Hello, World!")'
            },
            {
                'id': 'py_syntax_variables',
                'title': '📝 Синтаксис: Переменные',
                'difficulty': 'easy',
                'category': 'syntax',
                'description': 'Создайте переменную name со значением "Python" и выведите её',
                'function_name': None,
                'template': '# Напишите код здесь',
                'test_cases': [
                    {'input': [], 'expected': 'Python\n', 'type': 'output'}
                ],
                'hint': 'name = "Python"; print(name)',
                'solution': 'name = "Python"\nprint(name)'
            }
        ],
        'logic': [
            {
                'id': 'py_logic_even',
                'title': '🧠 Логика: Чётные числа',
                'difficulty': 'medium',
                'category': 'logic',
                'description': 'Напишите функцию is_even(n), которая возвращает True, если число чётное',
                'function_name': 'is_even',
                'template': 'def is_even(n):\n    # Напишите код здесь\n    pass',
                'test_cases': [
                    {'input': [2], 'expected': True},
                    {'input': [3], 'expected': False},
                    {'input': [0], 'expected': True},
                    {'input': [100], 'expected': True}
                ],
                'hint': 'Используйте оператор %',
                'solution': 'def is_even(n):\n    return n % 2 == 0'
            },
            {
                'id': 'py_logic_max',
                'title': '🧠 Логика: Максимум из трёх',
                'difficulty': 'medium',
                'category': 'logic',
                'description': 'Напишите функцию max_of_three(a, b, c), которая возвращает наибольшее число',
                'function_name': 'max_of_three',
                'template': 'def max_of_three(a, b, c):\n    # Напишите код здесь\n    pass',
                'test_cases': [
                    {'input': [1, 2, 3], 'expected': 3},
                    {'input': [10, 5, 7], 'expected': 10},
                    {'input': [-1, -5, 0], 'expected': 0}
                ],
                'hint': 'Используйте max() или сравнения',
                'solution': 'def max_of_three(a, b, c):\n    return max(a, b, c)'
            }
        ],
        'project': [
            {
                'id': 'py_project_calculator',
                'title': '🚀 Проект: Калькулятор',
                'difficulty': 'hard',
                'category': 'project',
                'description': 'Напишите функцию calculator(a, b, op), которая выполняет операцию op (+, -, *, /) над числами a и b',
                'function_name': 'calculator',
                'template': 'def calculator(a, b, op):\n    # Напишите код здесь\n    pass',
                'test_cases': [
                    {'input': [5, 3, '+'], 'expected': 8},
                    {'input': [10, 4, '-'], 'expected': 6},
                    {'input': [6, 7, '*'], 'expected': 42},
                    {'input': [15, 3, '/'], 'expected': 5.0}
                ],
                'hint': 'Используйте if-elif для проверки оператора',
                'solution': 'def calculator(a, b, op):\n    if op == "+":\n        return a + b\n    elif op == "-":\n        return a - b\n    elif op == "*":\n        return a * b\n    elif op == "/":\n        return a / b'
            },
            {
                'id': 'py_project_fibonacci',
                'title': '🚀 Проект: Числа Фибоначчи',
                'difficulty': 'hard',
                'category': 'project',
                'description': 'Напишите функцию fibonacci(n), которая возвращает n-е число Фибоначчи',
                'function_name': 'fibonacci',
                'template': 'def fibonacci(n):\n    # Напишите код здесь\n    pass',
                'test_cases': [
                    {'input': [0], 'expected': 0},
                    {'input': [1], 'expected': 1},
                    {'input': [5], 'expected': 5},
                    {'input': [10], 'expected': 55}
                ],
                'hint': 'Используйте цикл для вычисления',
                'solution': 'def fibonacci(n):\n    if n <= 1:\n        return n\n    a, b = 0, 1\n    for _ in range(n-1):\n        a, b = b, a + b\n    return b'
            }
        ]
    },
    
    'javascript': {
        'syntax': [
            {
                'id': 'js_syntax_hello',
                'title': '📝 Синтаксис: Вывод текста',
                'difficulty': 'easy',
                'category': 'syntax',
                'description': 'Напишите код, который выводит в консоль "Hello, World!"',
                'function_name': None,
                'template': '// Напишите код здесь\nconsole.log()',
                'test_cases': [
                    {'input': [], 'expected': 'Hello, World!\n', 'type': 'output'}
                ],
                'hint': 'Используйте console.log()',
                'solution': 'console.log("Hello, World!");'
            }
        ],
        'logic': [
            {
                'id': 'js_logic_even',
                'title': '🧠 Логика: Чётные числа',
                'difficulty': 'medium',
                'category': 'logic',
                'description': 'Напишите функцию isEven(n), которая возвращает true, если число чётное',
                'function_name': 'isEven',
                'template': 'function isEven(n) {\n    // Напишите код здесь\n}',
                'test_cases': [
                    {'input': [2], 'expected': True},
                    {'input': [3], 'expected': False},
                    {'input': [0], 'expected': True}
                ],
                'hint': 'Используйте оператор %',
                'solution': 'function isEven(n) {\n    return n % 2 === 0;\n}'
            }
        ],
        'project': [
            {
                'id': 'js_project_factorial',
                'title': '🚀 Проект: Факториал',
                'difficulty': 'hard',
                'category': 'project',
                'description': 'Напишите функцию factorial(n), которая возвращает факториал числа',
                'function_name': 'factorial',
                'template': 'function factorial(n) {\n    // Напишите код здесь\n}',
                'test_cases': [
                    {'input': [0], 'expected': 1},
                    {'input': [1], 'expected': 1},
                    {'input': [5], 'expected': 120}
                ],
                'hint': 'Используйте рекурсию или цикл',
                'solution': 'function factorial(n) {\n    if (n <= 1) return 1;\n    return n * factorial(n - 1);\n}'
            }
        ]
    },
    
    'java': {
        'syntax': [
            {
                'id': 'java_syntax_main',
                'title': '📝 Синтаксис: Hello World',
                'difficulty': 'easy',
                'category': 'syntax',
                'description': 'Напишите метод main, который выводит "Hello, World!"',
                'function_name': 'main',
                'template': 'public class Main {\n    public static void main(String[] args) {\n        // Напишите код здесь\n    }\n}',
                'test_cases': [
                    {'input': [], 'expected': 'Hello, World!\n', 'type': 'output'}
                ],
                'hint': 'Используйте System.out.println()',
                'solution': 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, World!");\n    }\n}'
            }
        ],
        'logic': [
            {
                'id': 'java_logic_max',
                'title': '🧠 Логика: Максимум',
                'difficulty': 'medium',
                'category': 'logic',
                'description': 'Напишите метод max(int a, int b), который возвращает большее число',
                'function_name': 'max',
                'template': 'public static int max(int a, int b) {\n    // Напишите код здесь\n}',
                'test_cases': [
                    {'input': [5, 3], 'expected': 5},
                    {'input': [2, 7], 'expected': 7},
                    {'input': [4, 4], 'expected': 4}
                ],
                'hint': 'Используйте if или Math.max()',
                'solution': 'public static int max(int a, int b) {\n    return Math.max(a, b);\n}'
            }
        ],
        'project': [
            {
                'id': 'java_project_sum',
                'title': '🚀 Проект: Сумма массива',
                'difficulty': 'hard',
                'category': 'project',
                'description': 'Напишите метод sumArray(int[] arr), который возвращает сумму всех элементов',
                'function_name': 'sumArray',
                'template': 'public static int sumArray(int[] arr) {\n    // Напишите код здесь\n}',
                'test_cases': [
                    {'input': [[1, 2, 3, 4, 5]], 'expected': 15},
                    {'input': [[10, 20, 30]], 'expected': 60},
                    {'input': [[-1, -2, -3]], 'expected': -6}
                ],
                'hint': 'Используйте цикл for',
                'solution': 'public static int sumArray(int[] arr) {\n    int sum = 0;\n    for (int i = 0; i < arr.length; i++) {\n        sum += arr[i];\n    }\n    return sum;\n}'
            }
        ]
    }
}

# ========= СОСТОЯНИЯ ДЛЯ FSM =========
class TrainingStates(StatesGroup):
    """Состояния тренировки"""
    choosing_language = State()
    choosing_mode = State()
    choosing_category = State()
    answering = State()
    solving_task = State()
    waiting_for_code = State()
    waiting_for_task_choice = State()

# ========= ИНИЦИАЛИЗАЦИЯ =========
logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# ========== РАБОТА С БАЗОЙ ДАННЫХ ==========
conn = sqlite3.connect('trainer.db', check_same_thread=False)
cursor = conn.cursor()

cursor.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        registered_at TEXT
    );
    
    CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        language TEXT,
        correct_answers INTEGER,
        total_questions INTEGER,
        date TEXT
    );
    
    CREATE TABLE IF NOT EXISTS user_sessions (
        user_id INTEGER PRIMARY KEY,
        language TEXT,
        question_index INTEGER,
        correct_count INTEGER,
        total_count INTEGER
    );
    
    CREATE TABLE IF NOT EXISTS task_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_id TEXT,
        code TEXT,
        passed_tests INTEGER,
        total_tests INTEGER,
        date TEXT
    );
''')
conn.commit()

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ ==========
def add_user(user_id, username, first_name):
    cursor.execute('INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?)',
                   (user_id, username, first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def start_session(user_id, language):
    cursor.execute('INSERT OR REPLACE INTO user_sessions VALUES (?, ?, 0, 0, ?)',
                   (user_id, language, len(QUESTIONS[language])))
    conn.commit()

def update_session(user_id, question_index, correct_count):
    cursor.execute('UPDATE user_sessions SET question_index = ?, correct_count = ? WHERE user_id = ?',
                   (question_index, correct_count, user_id))
    conn.commit()

def get_session(user_id):
    cursor.execute('SELECT * FROM user_sessions WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def end_session(user_id):
    cursor.execute('DELETE FROM user_sessions WHERE user_id = ?', (user_id,))
    conn.commit()

def save_stats(user_id, language, correct, total):
    cursor.execute('INSERT INTO stats (user_id, language, correct_answers, total_questions, date) VALUES (?, ?, ?, ?, ?)',
                   (user_id, language, correct, total, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()

def get_user_stats(user_id):
    cursor.execute('''
        SELECT language, correct_answers, total_questions, date 
        FROM stats 
        WHERE user_id = ? 
        ORDER BY date DESC
    ''', (user_id,))
    return cursor.fetchall()

def save_task_attempt(user_id, task_id, code, passed_tests, total_tests):
    cursor.execute('''
        INSERT INTO task_attempts (user_id, task_id, code, passed_tests, total_tests, date)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, task_id, code[:500], passed_tests, total_tests, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

# ========== СОЗДАНИЕ КЛАВИАТУР ==========
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Тренировка")],
            [
                KeyboardButton(text="📊 Статистика"),
                KeyboardButton(text="ℹ️ О боте")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )
    return keyboard

def get_languages_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Python", callback_data="lang_python"))
    builder.add(InlineKeyboardButton(text="JavaScript", callback_data="lang_javascript"))
    builder.add(InlineKeyboardButton(text="Java", callback_data="lang_java"))
    builder.adjust(2, 1)
    return builder.as_markup()

def get_modes_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="❓ Ответить на вопросы", callback_data="mode_questions"))
    builder.add(InlineKeyboardButton(text="📝 Решать задачи", callback_data="mode_tasks"))
    builder.adjust(1)
    return builder.as_markup()

def get_categories_keyboard(language):
    """Клавиатура выбора категории задач"""
    builder = InlineKeyboardBuilder()
    
    if language in TASKS:
        if TASKS[language].get('syntax'):
            builder.add(InlineKeyboardButton(
                text="📝 Синтаксис",
                callback_data=f"cat_syntax"
            ))
        if TASKS[language].get('logic'):
            builder.add(InlineKeyboardButton(
                text="🧠 Логика",
                callback_data=f"cat_logic"
            ))
        if TASKS[language].get('project'):
            builder.add(InlineKeyboardButton(
                text="🚀 Проекты",
                callback_data=f"cat_project"
            ))
    
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_modes"))
    builder.adjust(1)
    return builder.as_markup()

def get_tasks_keyboard(language, category):
    """Клавиатура выбора задачи из категории"""
    builder = InlineKeyboardBuilder()
    
    if language in TASKS and category in TASKS[language]:
        for task in TASKS[language][category]:
            difficulty_emoji = "🟢" if task['difficulty'] == 'easy' else "🟡" if task['difficulty'] == 'medium' else "🔴"
            builder.add(InlineKeyboardButton(
                text=f"{difficulty_emoji} {task['title']}",
                callback_data=f"task_{task['id']}"
            ))
    
    builder.add(InlineKeyboardButton(text="◀️ Назад к категориям", callback_data="back_to_categories"))
    builder.adjust(1)
    return builder.as_markup()

# ========== ФУНКЦИЯ ОТПРАВКИ ВОПРОСА ==========
async def send_question(user_id: int, language: str, q_index: int, state: FSMContext):
    questions = QUESTIONS[language]
    
    if q_index >= len(questions):
        session = get_session(user_id)
        if session:
            _, _, _, correct, total = session
            save_stats(user_id, language, correct, total)
            end_session(user_id)
            await state.clear()
            
            percent = (correct / total) * 100
            await bot.send_message(
                user_id,
                f"🎉 *Тренировка завершена!*\n\n"
                f"Язык: *{language.capitalize()}*\n"
                f"Результат: *{correct}/{total}* ({percent:.1f}%)\n\n"
                f"Хотите попробовать еще?",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        return
    
    q = questions[q_index]
    builder = InlineKeyboardBuilder()
    
    for i, option in enumerate(q['options']):
        builder.add(InlineKeyboardButton(
            text=option,
            callback_data=f"ans_{language}_{q_index}_{i}"
        ))
    
    builder.adjust(1)
    
    await bot.send_message(
        user_id,
        f"❓ *Вопрос {q_index + 1}/{len(questions)}*\n\n"
        f"{q['question']}",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await state.clear()
    await message.answer(
        f"👋 *Привет, {message.from_user.first_name}!*\n\n"
        f"Я бот-тренажер по программированию.\n\n"
        f"*Выбери действие:*",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "📚 Тренировка")
async def start_training(message: Message, state: FSMContext):
    await state.set_state(TrainingStates.choosing_language)
    await message.answer("Выбери язык программирования:", reply_markup=get_languages_keyboard())

@dp.message(F.text == "📊 Статистика")
async def show_stats(message: Message, state: FSMContext):
    stats = get_user_stats(message.from_user.id)
    
    if not stats:
        await message.answer(
            "📊 *У тебя пока нет завершенных тренировок.*",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return
    
    text = "📊 *Твоя статистика:*\n\n"
    for lang, correct, total, date in stats:
        percent = (correct / total * 100) if total > 0 else 0
        text += f"🔹 *{lang.capitalize()}*: {correct}/{total} ({percent:.1f}%)\n   📅 {date}\n\n"
    
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: Message, state: FSMContext):
    await message.answer(
        "🤖 *Тренажер по программированию*\n\n"
        "*Версия:* 2.0\n"
        "*Языки:* Python, JavaScript, Java\n\n"
        "*Режимы:*\n"
        "📝 Синтаксис - простые задачи на знание синтаксиса\n"
        "🧠 Логика - задачи на алгоритмическое мышление\n"
        "🚀 Проекты - комплексные задачи\n"
        "❓ Вопросы - теория\n\n"
        "*Проверка кода:*\n"
        "✅ Python - полная проверка\n"
        "✅ JavaScript - требует Node.js\n"
        "✅ Java - требует JDK\n\n"
        "Удачи в обучении! 🚀",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# ========== ОБРАБОТЧИКИ CALLBACK ==========
@dp.callback_query(F.data.startswith("lang_"))
async def process_language(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор языка"""
    language = callback.data.replace("lang_", "")
    
    # Проверяем, есть ли задачи и вопросы для этого языка
    if language in TASKS and language in QUESTIONS:
        await state.update_data(language=language)
        await state.set_state(TrainingStates.choosing_mode)
        
        await callback.message.edit_text(
            f"Выбран язык: *{language.capitalize()}*\n\nВыбери режим тренировки:",
            parse_mode="Markdown",
            reply_markup=get_modes_keyboard()
        )
    else:
        # Если языка нет в базе
        await callback.answer(
            f"Язык {language.capitalize()} скоро будет добавлен!",
            show_alert=True
        )
    
    await callback.answer()

@dp.callback_query(F.data == "back_to_modes")
async def back_to_modes(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TrainingStates.choosing_mode)
    await callback.message.edit_text("Выбери режим тренировки:", reply_markup=get_modes_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    language = data.get('language', 'python')
    await state.set_state(TrainingStates.choosing_category)
    await callback.message.edit_text(
        f"📚 *Выбери категорию задач для {language.capitalize()}:*",
        parse_mode="Markdown",
        reply_markup=get_categories_keyboard(language)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("mode_"))
async def process_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.replace("mode_", "")
    data = await state.get_data()
    language = data.get('language', 'python')
    
    if mode == "questions":
        start_session(callback.from_user.id, language)
        await state.set_state(TrainingStates.answering)
        await send_question(callback.from_user.id, language, 0, state)
    elif mode == "tasks":
        await state.set_state(TrainingStates.choosing_category)
        await callback.message.edit_text(
            f"📚 *Выбери категорию задач для {language.capitalize()}:*",
            parse_mode="Markdown",
            reply_markup=get_categories_keyboard(language)
        )
    
    await callback.answer()

@dp.callback_query(F.data.startswith("cat_"))
async def process_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("cat_", "")
    data = await state.get_data()
    language = data.get('language', 'python')
    
    await state.update_data(category=category)
    await state.set_state(TrainingStates.waiting_for_task_choice)
    
    category_names = {
        'syntax': '📝 Синтаксис',
        'logic': '🧠 Логика',
        'project': '🚀 Проекты'
    }
    
    await callback.message.edit_text(
        f"{category_names.get(category, category)} *для {language.capitalize()}:*\n\nВыбери задачу:",
        parse_mode="Markdown",
        reply_markup=get_tasks_keyboard(language, category)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("task_"))
async def process_task_choice(callback: CallbackQuery, state: FSMContext):
    task_id = callback.data.replace("task_", "")
    await state.update_data(current_task_id=task_id)
    
    # Получаем текущий язык и категорию
    data = await state.get_data()
    current_language = data.get('language', 'python')
    current_category = data.get('category', 'syntax')
    
    # Ищем задачу в нужном языке и категории
    task = None
    if current_language in TASKS and current_category in TASKS[current_language]:
        for t in TASKS[current_language][current_category]:
            if t['id'] == task_id:
                task = t
                break
    
    if task:
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="✏️ Написать решение", callback_data=f"solve_{task_id}"))
        builder.add(InlineKeyboardButton(text="💡 Подсказка", callback_data=f"hint_{task_id}"))
        builder.add(InlineKeyboardButton(text="◀️ Назад к задачам", callback_data="back_to_categories"))
        builder.adjust(1)
        
        difficulty_emoji = "🟢" if task['difficulty'] == 'easy' else "🟡" if task['difficulty'] == 'medium' else "🔴"
        
        await callback.message.edit_text(
            f"{difficulty_emoji} *{task['title']}*\n\n"
            f"📝 *Описание:*\n{task['description']}\n\n"
            f"⚙️ *Функция:* `{task['function_name'] if task['function_name'] else 'программа'}`\n\n"
            f"📊 *Тестов:* {len(task['test_cases'])}\n\n"
            f"Выбери действие:",
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
    else:
        await callback.answer("Задача не найдена", show_alert=True)
    
    await callback.answer()

@dp.callback_query(F.data.startswith("solve_"))
async def solve_task(callback: CallbackQuery, state: FSMContext):
    task_id = callback.data.replace("solve_", "")
    
    # Получаем текущий язык и категорию
    data = await state.get_data()
    current_language = data.get('language', 'python')
    current_category = data.get('category', 'syntax')
    
    # Ищем задачу в нужном языке и категории
    task = None
    if current_language in TASKS and current_category in TASKS[current_language]:
        for t in TASKS[current_language][current_category]:
            if t['id'] == task_id:
                task = t
                break
    
    if task:
        await state.update_data(current_task_id=task_id)
        await state.set_state(TrainingStates.waiting_for_code)
        
        template_lang = "python" if current_language == "python" else "javascript" if current_language == "javascript" else "java"
        
        await callback.message.edit_text(
            f"✏️ *Решение задачи: {task['title']}*\n\n"
            f"Напиши код и отправь его мне.\n\n"
            f"*Пример шаблона:*\n"
            f"```{template_lang}\n{task['template']}\n```\n\n"
            f"Отправь код и я проверю его!",
            parse_mode="Markdown"
        )
    else:
        await callback.answer("Задача не найдена", show_alert=True)
    
    await callback.answer()

@dp.callback_query(F.data.startswith("hint_"))
async def show_hint(callback: CallbackQuery, state: FSMContext):
    task_id = callback.data.replace("hint_", "")
    
    # Получаем текущий язык и категорию
    data = await state.get_data()
    current_language = data.get('language', 'python')
    current_category = data.get('category', 'syntax')
    
    # Ищем задачу в нужном языке и категории
    task = None
    if current_language in TASKS and current_category in TASKS[current_language]:
        for t in TASKS[current_language][current_category]:
            if t['id'] == task_id:
                task = t
                break
    
    if task and 'hint' in task:
        await callback.answer(task['hint'], show_alert=True)
    else:
        await callback.answer("Подсказка не найдена", show_alert=True)

@dp.callback_query(F.data.startswith("ans_"))
async def process_answer(callback: CallbackQuery, state: FSMContext):
    _, language, q_idx, ans_idx = callback.data.split("_")
    q_idx = int(q_idx)
    ans_idx = int(ans_idx)
    user_id = callback.from_user.id
    
    session = get_session(user_id)
    
    if not session:
        await callback.answer("Сессия истекла. Начни заново!", show_alert=True)
        await state.clear()
        return
    
    _, _, _, correct_count, _ = session
    is_correct = (ans_idx == QUESTIONS[language][q_idx]['correct'])
    
    if is_correct:
        correct_count += 1
        await callback.answer("✅ Правильно!")
    else:
        correct_answer = QUESTIONS[language][q_idx]['options'][QUESTIONS[language][q_idx]['correct']]
        await callback.answer(f"❌ Неправильно!\nПравильный ответ: {correct_answer}", show_alert=True)
    
    update_session(user_id, q_idx + 1, correct_count)
    await send_question(user_id, language, q_idx + 1, state)

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("Главное меню:", reply_markup=get_main_keyboard())
    await callback.answer()

# ========== ОБРАБОТЧИК ПОЛУЧЕНИЯ КОДА ==========
@dp.message(TrainingStates.waiting_for_code)
async def process_task_code(message: Message, state: FSMContext):
    code = message.text
    data = await state.get_data()
    task_id = data.get('current_task_id')
    selected_language = data.get('language', 'python')
    
    if not code.strip():
        await message.answer("Код не может быть пустым. Отправь код для проверки.")
        return
    
    # ОПРЕДЕЛЯЕМ РЕАЛЬНЫЙ ЯЗЫК КОДА
    detected_language = detect_language(code)
    
    # Проверяем, совпадает ли выбранный язык с реальным
    if detected_language != selected_language and detected_language != 'unknown':
        await message.answer(
            f"❌ *Несоответствие языка!*\n\n"
            f"Ты выбрал язык: *{selected_language.capitalize()}*\n"
            f"Но отправил код на языке: *{detected_language.capitalize()}*\n\n"
            f"Пожалуйста, выбери правильный язык или отправь код на {selected_language.capitalize()}.",
            parse_mode="Markdown"
        )
        return
    
    # Ищем задачу
    task = None
    if selected_language in TASKS:
        for category in TASKS[selected_language]:
            for t in TASKS[selected_language][category]:
                if t['id'] == task_id:
                    task = t
                    break
    
    if not task:
        await message.answer("❌ Задача не найдена")
        await state.clear()
        return
    
    status_msg = await message.answer(f"🔍 Проверяю код на {selected_language.capitalize()}...")
    
    # Проверяем код
    if selected_language == 'python':
        result = CodeChecker.check_python(code, task['function_name'], task['test_cases'])
    elif selected_language == 'javascript':
        if not shutil.which('node'):
            await status_msg.delete()
            await message.answer(
                "❌ *Node.js не установлен*\n\n"
                "Для проверки JavaScript кода требуется Node.js.\n"
                "Скачай и установи с [nodejs.org](https://nodejs.org/)",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            return
        result = CodeChecker.check_javascript(code, task['function_name'], task['test_cases'])
    elif selected_language == 'java':
        if not shutil.which('javac') or not shutil.which('java'):
            await status_msg.delete()
            await message.answer(
                "❌ *JDK не установлен*\n\n"
                "Для проверки Java кода требуется Java Development Kit.\n"
                "Скачай и установи с [oracle.com](https://www.oracle.com/java/technologies/downloads/)",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            return
        result = CodeChecker.check_java(code, task['function_name'], task['test_cases'])
    else:
        result = {'error': f'Язык {selected_language} не поддерживается'}
    
    await status_msg.delete()
    
    # Формируем ответ
    response = format_result_message(result, selected_language, task)
    
    # Кнопки для продолжения
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📝 Другие задачи", callback_data="back_to_categories"))
    builder.add(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"))
    builder.adjust(1)
    
    await message.answer(response, parse_mode="Markdown", reply_markup=builder.as_markup())
    
    # Сохраняем попытку
    if 'passed_count' in result and 'total_count' in result:
        save_task_attempt(
            message.from_user.id,
            task_id,
            code[:500],
            result['passed_count'],
            result['total_count']
        )

@dp.message()
async def handle_unknown(message: Message, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer(
            "Я не понимаю эту команду. Используй кнопки ниже:",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            "Пожалуйста, используй кнопки для навигации!",
            reply_markup=get_main_keyboard()
        )

# ========== ЗАПУСК БОТА ==========
async def main():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())