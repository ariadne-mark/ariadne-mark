/* Assessment subprocess only. Keep monotonic clocks and the host clock real. */
#define _GNU_SOURCE
#include <errno.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

static int assessment_realtime(struct timespec *out)
{
    const char *value = getenv("ARIADNE_ASSESSMENT_CLOCK");
    char *end;
    if (!value) {
        return syscall(SYS_clock_gettime, CLOCK_REALTIME, out);
    }
    errno = 0;
    long long seconds = strtoll(value, &end, 10);
    if (errno || end == value || *end != ':') {
        errno = EINVAL;
        return -1;
    }
    const char *fraction = end + 1;
    long nanos = strtol(fraction, &end, 10);
    if (errno || end == fraction || *end != '\0' || nanos < 0 || nanos >= 1000000000L) {
        errno = EINVAL;
        return -1;
    }
    out->tv_sec = (time_t) seconds;
    out->tv_nsec = nanos;
    return 0;
}

int clock_gettime(clockid_t clock, struct timespec *out)
{
    if (clock == CLOCK_REALTIME || clock == CLOCK_REALTIME_COARSE) {
        return assessment_realtime(out);
    }
    return syscall(SYS_clock_gettime, clock, out);
}

int gettimeofday(struct timeval *out, void *timezone)
{
    if (timezone) {
        struct timeval live_time;
        if (syscall(SYS_gettimeofday, &live_time, timezone) != 0) {
            return -1;
        }
    }
    struct timespec fixed;
    if (assessment_realtime(&fixed) != 0) {
        return -1;
    }
    out->tv_sec = fixed.tv_sec;
    out->tv_usec = fixed.tv_nsec / 1000;
    return 0;
}

time_t time(time_t *out)
{
    struct timespec fixed;
    if (assessment_realtime(&fixed) != 0) {
        return (time_t) -1;
    }
    if (out) {
        *out = fixed.tv_sec;
    }
    return fixed.tv_sec;
}
