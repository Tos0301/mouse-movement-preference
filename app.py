from flask import Flask, render_template, request, redirect, url_for, session
import random, time ,os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# 試行セット（4枚ずつ）
LEFT_IMAGES = [f'item{i}.jpg' for i in range(1, 5)]      # item1〜item4
RIGHT_IMAGES = [f'item{i}.jpg' for i in range(5, 9)]     # item5〜item8

TRIALS = [{'image': img, 'position': 'left'} for img in LEFT_IMAGES] + \
         [{'image': img, 'position': 'right'} for img in RIGHT_IMAGES]
random.shuffle(TRIALS)

@app.route('/')
def index():
    session['trials'] = TRIALS.copy()
    session['results'] = []
    return redirect(url_for('trial'))

@app.route('/trial', methods=['GET', 'POST'])
def trial():
    if 'trials' not in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        data = {
            'image': request.form['image'],
            'position': request.form['position'],
            'choice': request.form['choice'],
            'timestamp': time.time()
        }
        session['results'].append(data)
        session.modified = True

    if not session['trials']:
        return redirect(url_for('complete'))

    current = session['trials'].pop()
    session.modified = True

    # 使用するテンプレートを分岐
    if current['position'] == 'left':
        return render_template('left_trial.html', image=current['image'], position='left')
    else:
        return render_template('right_trial.html', image=current['image'], position='right')

@app.route('/complete')
def complete():
    return render_template('complete.html')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)