package watcher_test

import (
	"os"
	"path/filepath"
	"syscall"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/wandb/wandb/core/internal/waitingtest"
	"github.com/wandb/wandb/core/internal/watcher"
)

func mkdir(t *testing.T, path string) {
	require.NoError(t,
		os.MkdirAll(
			path,
			syscall.S_IRUSR|syscall.S_IWUSR|syscall.S_IXUSR,
		))
}

func writeFile(t *testing.T, path string, content string) {
	mkdir(t, filepath.Dir(path))

	require.NoError(t,
		os.WriteFile(path, []byte(content), syscall.S_IRUSR|syscall.S_IWUSR))
}

func waitWithDeadline[S any](t *testing.T, c <-chan S, msg string) S {
	select {
	case x := <-c:
		return x
	case <-time.After(5 * time.Second):
		t.Fatal("took too long: " + msg)
		panic("unreachable")
	}
}

func TestWatcher(t *testing.T) {
	newTestWatcher := func() (watcher.Watcher, *waitingtest.FakeStopwatch) {
		fakeStopwatch := waitingtest.NewFakeStopwatch()
		return watcher.New(watcher.Params{
			PollingStopwatch: fakeStopwatch,
		}), fakeStopwatch
	}

	finishWithDeadline := func(t *testing.T, w watcher.Watcher) {
		finished := make(chan struct{})

		go func() {
			w.Finish()
			finished <- struct{}{}
		}()

		waitWithDeadline(t, finished, "expected Finish() to complete")
	}

	t.Run("runs callback on file write", func(t *testing.T) {
		onChangeChan := make(chan struct{})
		file := filepath.Join(t.TempDir(), "file.txt")
		writeFile(t, file, "")
		watcher, pollingStopwatch := newTestWatcher()
		defer finishWithDeadline(t, watcher)

		require.NoError(t,
			watcher.Watch(file, func() { onChangeChan <- struct{}{} }))
		writeFile(t, file, "xyz")
		pollingStopwatch.SetDone()

		waitWithDeadline(t, onChangeChan,
			"expected file callback to be called")
	})

	t.Run("runs callback on new file in directory", func(t *testing.T) {
		onChangeChan := make(chan string)
		dir := filepath.Join(t.TempDir(), "dir")
		file := filepath.Join(dir, "file.txt")
		mkdir(t, dir)
		watcher, pollingStopwatch := newTestWatcher()
		defer finishWithDeadline(t, watcher)

		require.NoError(t,
			watcher.WatchTree(dir, func(s string) { onChangeChan <- s }))
		writeFile(t, file, "")
		pollingStopwatch.SetDone()

		result := waitWithDeadline(t, onChangeChan,
			"expected file callback to be called")
		assert.Equal(t, result, file)
	})

	t.Run("runs callback on deleted file in directory", func(t *testing.T) {
		onChangeChan := make(chan string)
		dir := filepath.Join(t.TempDir(), "dir")
		file := filepath.Join(dir, "file.txt")
		writeFile(t, file, "")
		watcher, pollingStopwatch := newTestWatcher()
		defer finishWithDeadline(t, watcher)

		require.NoError(t,
			watcher.WatchTree(dir, func(s string) { onChangeChan <- s }))
		require.NoError(t, os.Remove(file))
		pollingStopwatch.SetDone()

		result := waitWithDeadline(t, onChangeChan,
			"expected file callback to be called")
		assert.Equal(t, result, file)
	})
}
