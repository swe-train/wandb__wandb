import wandb
import numpy as np
import pytest
import PIL
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from click.testing import CliRunner

data = np.random.randint(255, size=(1000))


def test_raw_data():
    wbhist = wandb.Histogram(data)
    assert len(wbhist.histogram) == 64


def test_np_histogram():
    wbhist = wandb.Histogram(np_histogram=np.histogram(data))
    assert len(wbhist.histogram) == 10


def test_manual_histogram():
    wbhist = wandb.Histogram(np_histogram=([1, 2, 4], [3, 10, 20, 0]))
    assert len(wbhist.histogram) == 3


def test_invalid_histogram():
    with pytest.raises(ValueError):
        wbhist = wandb.Histogram(np_histogram=([1, 2, 3], [1]))


def test_histogram_to_json():
    wbhist = wandb.Histogram(data)
    json = wbhist.to_json()
    assert json["_type"] == "histogram"
    assert len(json["values"]) == 64


image = np.zeros((28, 28))


def test_captions():
    wbone = wandb.Image(image, caption="Cool")
    wbtwo = wandb.Image(image, caption="Nice")
    assert wandb.Image.captions([wbone, wbtwo]) == ["Cool", "Nice"]


def test_transform():
    with CliRunner().isolated_filesystem():
        run = wandb.wandb_run.Run()
        wb_image = wandb.Image(image)
        meta = wandb.Image.seq_to_json([wb_image], run, "test", 'summary')
        assert os.path.exists(os.path.join(run.dir, meta['images'][0]['path']))
        del meta['images'][0]['entity']
        del meta['images'][0]['project']
        del meta['images'][0]['sha256']
        del meta['images'][0]['run']
        #del meta['images'][0]['size']
        #del meta['images'][0]['entity']
        assert meta == {
            '_type': 'images',
            'count': 1,
            'height': 28,
            'width': 28,
            'images': [{
                '_type': 'image',
                'height': 28,
                'path': 'media/images/test_summary_0.png',
                'size': 73,
                'width': 28
            }],
        }


def test_audio_sample_rates():
    audio1 = np.random.uniform(-1, 1, 44100)
    audio2 = np.random.uniform(-1, 1, 88200)
    wbaudio1 = wandb.Audio(audio1, sample_rate=44100)
    wbaudio2 = wandb.Audio(audio2, sample_rate=88200)
    assert wandb.Audio.sample_rates([wbaudio1, wbaudio2]) == [44100, 88200]
    # test with missing sample rate
    with pytest.raises(ValueError):
        wbaudio3 = wandb.Audio(audio1)


def test_audio_durations():
    audio1 = np.random.uniform(-1, 1, 44100)
    audio2 = np.random.uniform(-1, 1, 88200)
    wbaudio1 = wandb.Audio(audio1, sample_rate=44100)
    wbaudio2 = wandb.Audio(audio2, sample_rate=44100)
    assert wandb.Audio.durations([wbaudio1, wbaudio2]) == [1.0, 2.0]


def test_audio_captions():
    audio = np.random.uniform(-1, 1, 44100)
    sample_rate = 44100
    caption1 = "This is what a dog sounds like"
    caption2 = "This is what a chicken sounds like"
    # test with all captions
    wbaudio1 = wandb.Audio(audio, sample_rate=sample_rate, caption=caption1)
    wbaudio2 = wandb.Audio(audio, sample_rate=sample_rate, caption=caption2)
    assert wandb.Audio.captions([wbaudio1, wbaudio2]) == [caption1, caption2]
    # test with no captions
    wbaudio3 = wandb.Audio(audio, sample_rate=sample_rate)
    wbaudio4 = wandb.Audio(audio, sample_rate=sample_rate)
    assert wandb.Audio.captions([wbaudio3, wbaudio4]) == False
    # test with some captions
    wbaudio5 = wandb.Audio(audio, sample_rate=sample_rate)
    wbaudio6 = wandb.Audio(audio, sample_rate=sample_rate, caption=caption2)
    assert wandb.Audio.captions([wbaudio5, wbaudio6]) == ['', caption2]


def test_audio_to_json():
    audio = np.zeros(44100)
    with CliRunner().isolated_filesystem():
        run = wandb.wandb_run.Run()
        meta = wandb.Audio.seq_to_json(
            [wandb.Audio(audio, sample_rate=44100)], run, "test", 0)
        assert os.path.exists(os.path.join(run.dir, meta['audio'][0]['path']))
        del meta['audio'][0]['run']
        del meta['audio'][0]['path']
        del meta['audio'][0]['sha256']
        del meta['audio'][0]['entity']
        del meta['audio'][0]['project']
        assert meta == {
            '_type': 'audio',
            'count': 1,
            'sampleRates': [44100],
            'durations': [1.0],
            'audio': [{
                '_type': 'audio-file',
                'caption': None,
                'sample_rate': 44100,
                'size': 88244,
            }],
        }


def test_guess_mode():
    image = np.random.randint(255, size=(28, 28, 3))
    wbimg = wandb.Image(image)
    assert wbimg._image.mode == "RGB"


def test_pil():
    pil = PIL.Image.new("L", (28, 28))
    img = wandb.Image(pil)
    assert img._image == pil


def test_matplotlib_image():
    plt.plot([1, 2, 2, 4])
    img = wandb.Image(plt)
    assert img._image.width == 640


def test_html_str():
    with CliRunner().isolated_filesystem():
        run = wandb.wandb_run.Run()
        html = wandb.Html("<html><body><h1>Hello</h1></body></html>")
        wandb.Html.seq_to_json([html], run, "rad", "summary")
        assert os.path.exists(os.path.join(run.dir, "media/html/rad_summary_0.html"))


def test_html_styles():
    with CliRunner().isolated_filesystem():
        pre = '<base target="_blank"><link rel="stylesheet" type="text/css" href="https://app.wandb.ai/normalize.css" />'
        html = wandb.Html("<html><body><h1>Hello</h1></body></html>")
        assert html.html == "<html><head>"+pre + \
            "</head><body><h1>Hello</h1></body></html>"
        html = wandb.Html(
            "<html><head></head><body><h1>Hello</h1></body></html>")
        assert html.html == "<html><head>"+pre + \
            "</head><body><h1>Hello</h1></body></html>"
        html = wandb.Html("<h1>Hello</h1>")
        assert html.html == pre + "<h1>Hello</h1>"
        html = wandb.Html("<h1>Hello</h1>", inject=False)
        assert html.html == "<h1>Hello</h1>"


def test_html_file():
    with CliRunner().isolated_filesystem():
        run = wandb.wandb_run.Run()
        with open("test.html", "w") as f:
            f.write("<html><body><h1>Hello</h1></body></html>")
        html = wandb.Html(open("test.html"))
        wandb.Html.seq_to_json([html, html], run, "rad", "summary")
        assert os.path.exists(os.path.join(run.dir, "media/html/rad_summary_0.html"))
        assert os.path.exists(os.path.join(run.dir, "media/html/rad_summary_0.html"))


def test_table_default():
    table = wandb.Table()
    table.add_data("Some awesome text", "Positive", "Negative")
    assert table.to_json() == {
        "_type": "table",
        "data": [["Some awesome text", "Positive", "Negative"]],
        "columns": ["Input", "Output", "Expected"]
    }


def test_table_custom():
    table = wandb.Table(["Foo", "Bar"])
    table.add_data("So", "Cool")
    table.add_row("&", "Rad")
    assert table.to_json() == {
        "_type": "table",
        "data": [["So", "Cool"], ["&", "Rad"]],
        "columns": ["Foo", "Bar"]
    }


def test_table_init():
    table = wandb.Table(data=[["Some awesome text", "Positive", "Negative"]])
    assert table.to_json() == {"_type": "table",
                                "data": [["Some awesome text", "Positive", "Negative"]],
                                "columns": ["Input", "Output", "Expected"]}
