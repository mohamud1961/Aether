#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t terminate_requested = 0;
static volatile sig_atomic_t terminate_signal = SIGTERM;

static void on_signal(int sig) {
    terminate_requested = 1;
    terminate_signal = sig;
}

static int write_text(const char *path, const char *text) {
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return -1;
    size_t n = strlen(text);
    ssize_t w = write(fd, text, n);
    int saved = errno;
    close(fd);
    errno = saved;
    return (w == (ssize_t)n) ? 0 : -1;
}

static int read_children(pid_t pid, pid_t *out, int cap) {
    char path[128];
    snprintf(path, sizeof(path), "/proc/%ld/task/%ld/children", (long)pid, (long)pid);
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    int n = 0;
    while (n < cap && fscanf(f, "%d", &out[n]) == 1) n++;
    fclose(f);
    return n;
}

static int process_exists(pid_t pid) {
    if (pid <= 0) return 0;
    if (kill(pid, 0) == 0) return 1;
    return errno == EPERM;
}

static int collect_descendants(pid_t root, pid_t *out, int cap) {
    pid_t queue[4096];
    int qh = 0, qt = 0, n = 0;
    queue[qt++] = root;
    while (qh < qt && qt < (int)(sizeof(queue)/sizeof(queue[0]))) {
        pid_t cur = queue[qh++];
        pid_t kids[1024];
        int k = read_children(cur, kids, 1024);
        for (int i = 0; i < k; i++) {
            pid_t child = kids[i];
            int seen = 0;
            for (int j = 0; j < n; j++) if (out[j] == child) { seen = 1; break; }
            if (seen) continue;
            if (n < cap) out[n++] = child;
            if (qt < (int)(sizeof(queue)/sizeof(queue[0]))) queue[qt++] = child;
        }
    }
    return n;
}

static void signal_descendants(pid_t root, int sig) {
    pid_t pids[4096];
    int n = collect_descendants(root, pids, 4096);
    /* Deepest/newest children first is friendlier for tree shutdown. */
    for (int i = n - 1; i >= 0; i--) if (process_exists(pids[i])) kill(pids[i], sig);
}

static int descendants_alive(pid_t root) {
    pid_t pids[4096];
    int n = collect_descendants(root, pids, 4096);
    for (int i = 0; i < n; i++) if (process_exists(pids[i])) return 1;
    return 0;
}

static void sleep_ms(long ms) {
    struct timespec ts;
    ts.tv_sec = ms / 1000;
    ts.tv_nsec = (ms % 1000) * 1000000L;
    while (nanosleep(&ts, &ts) != 0 && errno == EINTR) {}
}

static int cleanup_all_descendants(const char *cleanup_path) {
    pid_t self = getpid();
    /* The action deadline has already expired. Kill all descendants immediately
       so no daemonised child receives a post-timeout mutation grace period. */
    signal_descendants(self, SIGKILL);
    for (int i = 0; i < 60; i++) {
        while (waitpid(-1, NULL, WNOHANG) > 0) {}
        if (!descendants_alive(self)) {
            if (write_text(cleanup_path, "ok\n") != 0) return 126;
            return 0;
        }
        sleep_ms(25);
        signal_descendants(self, SIGKILL);
    }
    write_text(cleanup_path, "failed\n");
    return 125;
}

int main(int argc, char **argv) {
    if (argc != 5) {
        fprintf(stderr, "usage: %s EXIT_PATH CLEANUP_PATH CWD COMMAND\n", argv[0]);
        return 64;
    }
    const char *exit_path = argv[1];
    const char *cleanup_path = argv[2];
    const char *cwd = argv[3];
    const char *command = argv[4];

    if (prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0) {
        perror("prctl(PR_SET_CHILD_SUBREAPER)");
        return 126;
    }
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sigemptyset(&sa.sa_mask);
    sa.sa_handler = on_signal;
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGHUP, &sa, NULL);

    if (chdir(cwd) != 0) {
        perror("chdir");
        return 125;
    }

    pid_t child = fork();
    if (child < 0) {
        perror("fork");
        return 126;
    }
    if (child == 0) {
        signal(SIGTERM, SIG_DFL);
        signal(SIGINT, SIG_DFL);
        signal(SIGHUP, SIG_DFL);
        execl("/bin/bash", "bash", "-lc", command, (char *)NULL);
        perror("exec /bin/bash");
        _exit(127);
    }

    int status = 0;
    for (;;) {
        pid_t got = waitpid(child, &status, 0);
        if (got == child) break;
        if (got < 0 && errno == EINTR) {
            if (terminate_requested) break;
            continue;
        }
        if (got < 0 && errno == ECHILD) break;
        if (got < 0) {
            perror("waitpid");
            return 126;
        }
    }

    if (terminate_requested) {
        int cleanup = cleanup_all_descendants(cleanup_path);
        if (cleanup != 0) return cleanup;
        return 128 + terminate_signal;
    }

    int code = 125;
    if (WIFEXITED(status)) code = WEXITSTATUS(status);
    else if (WIFSIGNALED(status)) code = 128 + WTERMSIG(status);
    char buf[64];
    snprintf(buf, sizeof(buf), "%d\n", code);
    if (write_text(exit_path, buf) != 0) {
        perror("write exit status");
        return 126;
    }
    return code;
}
