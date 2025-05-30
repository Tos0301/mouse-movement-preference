
from flask import Flask, render_template, request, redirect, url_for, session
import random, time, os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

IMAGES = [f'item{i}.jpg' for i in range(1, 25)]  # 24枚
TRIALS = [{'image': img, 'position': 'left'} for img in IMAGES[:12]] + \
         [{'image': img, 'position': 'right'} for img in IMAGES[12:]]
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

    if not session['trials']:
        return redirect(url_for('complete'))

    current = session['trials'].pop()
    return render_template('trial.html', image=current['image'], position=current['position'])

@app.route('/complete')
def complete():
    return render_template('complete.html', results=session['results'])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)