import os
import json
import time
import random
import requests
from collections import Counter
from flask import Flask, redirect, request, render_template
from ast import literal_eval
from pathlib import Path

app = Flask(__name__)
data_path = './data'
output_path = '/mnt/nas2/haneul/language_learner_annotation/ner_test'
# output_path = '/Volumes/share/haneul/language_learner_annotation/ner_test'
# output_path = './output'
context_count_per_user = 5
user_count_per_context = 3
secret_code = 'done_'


def init_paths():
    paths = [
        '%s/contexts' % data_path,
        '%s' %output_path,
        '%s/annotation-output' %output_path,
        '%s/annotation-output/response' % output_path,
        '%s/annotation-output/no_response' % output_path,
        '%s/user_ids' % output_path,
        '%s/pretest-output' %output_path,
        '%s/posttest-output' %output_path
    ]
    for path in paths:
        if not os.path.exists(path):
            os.makedirs(path)

def get_all_context_ids():
    context_filenames = os.listdir('%s/contexts' % data_path)
    context_ids = []
    for filename in context_filenames:
        if filename.endswith('.json'):
            filename_strip = filename[:-5]
            context_ids.append(filename_strip)
    return context_ids


def get_context_response_count_dict():
    context_ids = get_all_context_ids()
    response_filenames = os.listdir('%s/annotation-output/response' % output_path)
    counter = {cid: 0 for cid in context_ids}
    for filename in response_filenames:
        if '__res__' not in filename:
            continue
        split_filename = filename.split('__res__')
        if len(split_filename) != 2 or not split_filename[1].endswith('.json'):
            continue
        context_id = split_filename[0]
        counter[context_id] += 1
    return counter


def draw_context_ids():
    count_dict = get_context_response_count_dict()
    context_ids = []
    while len(context_ids) < context_count_per_user:
        # Draw a context that currently has minimum number of responses.
        valid_counts = [count for cid, count in count_dict.items() if cid not in context_ids]
        if not valid_counts:
            break
        min_count = min(valid_counts)
        draw_box = [cid for cid, count in count_dict.items() if (count == min_count) and (cid not in context_ids)]
        context_ids.append(random.choice(draw_box))

    return context_ids


def get_context_dict(context_id):
    file_path = '%s/contexts/%s.json' % (data_path, context_id)
    with open(file_path, 'r') as f:
        context_dict = json.load(f)
    if 'id' not in context_dict:
        context_dict['id'] = context_id
    return context_dict


def get_questions():
    json_url = requests.get('https://sheets.googleapis.com/v4/spreadsheets/1DPQnBmAQtJ0pCYGgD7dSmoN8EUKWU10eGUjPJ76B5TE/values/question/?alt=json&key=AIzaSyAQRP6ZxaLICxsOCQowChrdDfghUASYzcs').json()['values']
    header = json_url[0]
    questions = [dict(zip(header, v)) for v in json_url[1:]]
    for i in range(len(questions)):
        questions[i]['option'] = literal_eval(questions[i]['option'])
    return questions


def get_validate_texts():
    with open('%s/validate_texts.json' % data_path, 'r') as f:
        validate_texts = json.load(f)
    return validate_texts

def draw_question_ids_over_limit():
    response_ids = [x.name for x in list(Path(output_path + '/annotation-output').glob('**/*__res__*.json'))]
    response_counter = Counter(response_ids)
    return [k for k, v in response_counter.items() if v >= user_count_per_context]


def draw_context_dicts(language_task_set, workerId):

    json_url = requests.get('https://sheets.googleapis.com/v4/spreadsheets/1DPQnBmAQtJ0pCYGgD7dSmoN8EUKWU10eGUjPJ76B5TE/values/dataset-ner/?alt=json&key=AIzaSyAQRP6ZxaLICxsOCQowChrdDfghUASYzcs').json()['values']

    header = json_url[0]
    
    questions = json_url[1:]
    random.shuffle(questions)
    questions_over_limit = draw_question_ids_over_limit()
    responses = [x.name.split('__res__')[0] for x in list(Path(output_path + '/annotation-output').glob('**/*__res__*.json')) if workerId in x.name]
    questions = [q for q in questions if q[3] not in questions_over_limit and [q[2], q[0]] in [language_task_set] and q[3] not in responses]
    questions = questions[:min(context_count_per_user, len(questions))]

    questions = [dict(zip(header, v)) for v in questions]
    for question in questions:
        test_qns = json.loads(question['test_qns'])
        test_qns_generated = json.loads(question['test_qns_generated'])
        random_index = random.randint(0, len(test_qns_generated) - 1)
        question['test_qns_generated'] = json.dumps(test_qns_generated[random_index])
        question['test_qns'] = json.dumps(test_qns[0])

    return questions


def is_user_id(uid):
    file_path = '%s/user_ids/%s.json' % (output_path, uid)
    return os.path.exists(file_path)


def generate_user_id():
    while True:
        uid = ''.join(random.choice('abcedfghijklmnopqrstuvwxyz0123456789') for i in range(16))
        if not is_user_id(uid):
            break
    file_path = '%s/user_ids/%s.json' % (output_path, uid)
    with open(file_path, 'w') as f:
        f.write('!')
    return uid


def save_test(res_output_path, context_id, user_id, response, isPassed, workerId, start_time, end_time, test_type, translation, context):
    if isPassed:
        file_path = '%s/%s__res__%s__%s__%s.json' % (res_output_path, context_id, user_id, workerId, test_type)
    else:
        file_path = '%s/no_pass__%s__res__%s__%s__%s.json' % (res_output_path, context_id, user_id, workerId, test_type)
    qns = [x['test_qns'] for x in context]
    qns_generated = [x['test_qns_generated'] for x in context]
    data = {
        'context_id': context_id,
        'user_id': user_id,
        'response': response,
        'worker_id': workerId,
        'start_time': start_time,
        'end_time': end_time,
        'translation': translation,
        'qns': qns,
        'qns_generated': qns_generated,
    }
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=4))


def save_response(res_output_path, context_id, user_id, response, ground_truth, isPassed, workerId, start_time, end_time, translation):
    if isPassed:
        file_path = '%s/%s__res__%s__%s.json' % (res_output_path, context_id, user_id, workerId)
    else:
        file_path = '%s/no_pass__%s__res__%s__%s.json' % (res_output_path, context_id, user_id, workerId)
    data = {
        'context_id': context_id,
        'user_id': user_id,
        'response': response,
        'ground_truth': ground_truth,
        'worker_id': workerId,
        'start_time': start_time,
        'end_time': end_time,
        'translation': translation
    }
    with open(file_path, 'w') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=4))


def get_language_task_set():
    json_url = requests.get('https://sheets.googleapis.com/v4/spreadsheets/1DPQnBmAQtJ0pCYGgD7dSmoN8EUKWU10eGUjPJ76B5TE/values/dataset-ner/?alt=json&key=AIzaSyAQRP6ZxaLICxsOCQowChrdDfghUASYzcs').json()['values']
    language_task_set = list(set((row[2], row[0]) for row in json_url[1:]))
    return language_task_set


@app.route('/')
def index():
    return render_template('task_index.html')


@app.route('/tasks')
def task_index():
    language_task_set = sorted(get_language_task_set())
    return render_template('task_instruction.html',
        language_task_set=language_task_set)
    return render_template('task_index.html')


@app.route('/tasks/test', methods=['POST'])
def task_test():
    data = json.loads(request.data)
    test_type = data['test_type']
    if (test_type == 'pre'):
        workerId = data['workerId']
        language_task_set = data['language_task_set']
        isTranslation = data['isTranslation']
        uid = generate_user_id()
        context_dicts = draw_context_dicts(language_task_set, workerId)
        questions = get_questions()
        validate_texts = get_validate_texts()
    else:
        workerId = data['workerId']
        isTranslation = data['isTranslation']
        uid = data['uid']
        context_dicts = data['context_dicts']
        questions = data['questions']
        validate_texts = 'asssssss'
    return render_template('task_test.html',
        test_type=test_type,
        isTranslation=isTranslation,
        uid=uid,
        contexts=context_dicts,
        questions=questions,
        validate_texts=validate_texts,
        workerId=workerId)

@app.route('/tasks/draw', methods=['POST'])
def task_draw():
    data = json.loads(request.data)
    workerId = data['workerId']
    language_task_set = data['language_task_set']
    isTranslation = data['isTranslation']
    uid = generate_user_id()
    questions = get_questions()
    validate_texts = get_validate_texts()
    return render_template('task_draw.html',
        isTranslation=isTranslation,
        uid=uid,
        contexts=context_dicts,
        questions=questions,
        validate_texts=validate_texts,
        workerId=workerId)

@app.route('/tasks/testSubmit', methods=['POST'])
def test_submit():
    data = json.loads(request.data)
    context = data['context']
    response = data['response']
    user_id = data['uid']
    isPassed = data['isPassed']
    workerId = data['workerId']
    start_time = data['start_time']
    end_time = data['end_time']
    translation = data['translation']
    questions = data['questions']
    isTranslation = data['isTranslation']
    validate_texts = data['validateTexts']
    test_type = data['testType']

    context_dict = context[0]
    r = response
    res_output_path = output_path + "/" + test_type + "test-output/" if r else output_path + "/" + test_type + "test-output/"
    save_test(res_output_path, context_dict['id'], user_id, r, isPassed, workerId, start_time, end_time, test_type, translation[context_dict['id']], context)
    
    if test_type == 'pre':
        return render_template('task_draw.html',
            isTranslation=isTranslation,
            uid=user_id,
            contexts=context,
            questions=questions,
            validate_texts=validate_texts,
            workerId=workerId)
    else:
        return 'done:%s' % (secret_code + user_id)


@app.route('/tasks/submit', methods=['POST'])
def task_submit():
    data = json.loads(request.data)
    context = data['context']
    response = data['response']
    user_id = data['uid']
    isPassed = data['isPassed']
    workerId = data['workerId']
    start_time = data['start_time']
    end_time = data['end_time']
    translation = data['translation']

    for context_dict in context:
        r = response[context_dict['id']] if context_dict['id'] in response else None
        json_url = requests.get('https://sheets.googleapis.com/v4/spreadsheets/1DPQnBmAQtJ0pCYGgD7dSmoN8EUKWU10eGUjPJ76B5TE/values/dataset-ner/?alt=json&key=AIzaSyAQRP6ZxaLICxsOCQowChrdDfghUASYzcs').json()['values']
        language_task_set = list(set((row[2], row[0]) for row in json_url[1:]))
        gt = [row[4] for row in json_url[1:] if row[3] == context_dict['id']]
        gt = gt[0] if gt else None
        res_output_path = output_path + "/annotation-output/response/" if r else output_path + "/annotation-output/no_response/"
        save_response(res_output_path, context_dict['id'], user_id, r, gt, isPassed, workerId, start_time, end_time, translation[context_dict['id']])

    return 'done:%s' % (secret_code + user_id)


@app.route('/tasks/done')
def task_done():
    code = request.args.get('code')
    return render_template('task_done.html', code=code)


init_paths()
if __name__ == '__main__':
    # gunicorn_error_logger = logging.getLogger('gunicorn.error')
    # app.logger.handlers.extend(gunicorn_error_logger.handlers)
    # app.logger.setLevel(logging.DEBUG)
    # app.logger.debug('this will show in the log')
    app.logger.addHandler(logging.StreamHandler(sys.stdout))
    app.logger.setLevel(logging.DEBUG)

    app.run(debug=True)