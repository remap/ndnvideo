/*****************************************************************************
 * Preamble
 *****************************************************************************/

#include <Python.h>
/*
#include <python/bytesobject.h>
 */

#ifdef HAVE_CONFIG_H
#    include "config.h"
#endif

#include <limits.h>

#include <vlc_common.h>
#include <vlc_plugin.h>
#include <vlc_access.h>
#include <vlc_url.h>

#define PYTHON_SCRIPT "access.py"

struct access_sys_t {
	PyObject *callback_open;
	PyObject *callback_close;
	PyObject *callback_control;
	PyObject *callback_block;
};

static struct access_sys_t *g_sys;

/*****************************************************************************
 * Disable internationalization
 *****************************************************************************/
#define _(str) (str)
#define N_(str) (str)

/*****************************************************************************
 * Local prototypes.
 *****************************************************************************/

static int Open(vlc_object_t *);
static void Close(vlc_object_t *);
static int Control(access_t *p_access, int i_query, va_list args);
static block_t *Block(access_t *p_access);

static PyObject *
access_set_callback(PyObject *self, PyObject *args)
{
	int r;
	const char *type;
	PyObject *callback;

	assert(g_sys);

	r = PyArg_ParseTuple(args, "sO:set_callback", &type, &callback);
	if (r < 0)
		return NULL;

	if (!PyCallable_Check(callback)) {
		PyErr_SetString(PyExc_ValueError, "argument needs to be callable");
		return NULL;
	}

	if (!strcmp(type, "open")) {
		Py_XDECREF(g_sys->callback_open);
		Py_INCREF(callback);
		g_sys->callback_open = callback;
	} else if (!strcmp(type, "close")) {
		Py_XDECREF(g_sys->callback_close);
		Py_INCREF(callback);
		g_sys->callback_close = callback;
	} else if (!strcmp(type, "control")) {
		Py_XDECREF(g_sys->callback_control);
		Py_INCREF(callback);
		g_sys->callback_control = callback;
	} else if (!strcmp(type, "block")) {
		Py_XDECREF(g_sys->callback_block);
		Py_INCREF(callback);
		g_sys->callback_block = callback;
	} else {
		PyErr_Format(PyExc_ValueError, "invalid type: %s", type);
		return NULL;
	}

	Py_RETURN_NONE;
}

static PyMethodDef AccessMethods[] = {
	{"set_callback", access_set_callback, METH_VARARGS,
		"Set callbacks for access module"},
	{NULL, NULL, 0, NULL}
};

/*****************************************************************************
 * Module descriptor
 *****************************************************************************/

#define SCRIPT_TEXT N_("Script")
#define SCRIPT_LONG_TEXT N_("Python script filename")

vlc_module_begin();

set_shortname(N_("Python"));
set_description(N_("Python input"));
set_category(CAT_INPUT);
set_subcategory(SUBCAT_INPUT_ACCESS);

add_string("python-script", "access.py", NULL, SCRIPT_TEXT, SCRIPT_LONG_TEXT,
		false);

change_safe();
set_capability("access", 60);
add_shortcut("pyccn");
set_callbacks(Open, Close);

vlc_module_end();

/*****************************************************************************
 * Open: initialize interface
 *****************************************************************************/
static int
Open(vlc_object_t *p_this)
{
	access_t *p_access = (access_t *) p_this;
	FILE *fp;
	PyObject *res;
	int r;

	if (g_sys) {
		msg_Err(p_access, "Only one instance is allowed");
		return VLC_EGENERIC;
	}

	access_InitFields(p_access);
	ACCESS_SET_CALLBACKS(NULL, Block, Control, NULL);

	msg_Info(p_this, "!!!! Python !!!! Got open request for name: %s",
			p_access->psz_path);

	g_sys = calloc(1, sizeof(struct access_sys_t));
	if (!g_sys)
		return VLC_ENOMEM;

	assert(p_access->p_sys == NULL);
	p_access->p_sys = g_sys;

	Py_Initialize();
	res = Py_InitModule("vlc_access", AccessMethods);
	if (!res)
		goto error;

	fp = fopen(PYTHON_SCRIPT, "r");
	if (fp == NULL) {
		PyErr_SetFromErrnoWithFilename(PyExc_IOError, PYTHON_SCRIPT);
		goto error;
	}

	r = PyRun_SimpleFileEx(fp, PYTHON_SCRIPT, true);
	if (r < 0)
		goto error;

	return VLC_SUCCESS;

error:
	PyErr_Print();
	Py_Finalize();
	return VLC_EGENERIC;
}

/*****************************************************************************
 * Close: destroy interface
 *****************************************************************************/
static void
Close(vlc_object_t *p_this)
{
	access_t *p_access = (access_t *) p_this;

	msg_Info(p_this, "!!!! Python !!!! Got close request");

	if (PyErr_Occurred())
		PyErr_Print();

	Py_Finalize();

	free(p_access->p_sys);
	vlc_object_kill(p_this);
	g_sys = NULL;
}

static int
Control(access_t *p_access, int i_query, va_list args)
{
	bool *bp_bool;
	int64_t *pi_64;

	msg_Info(p_access, "!!!! Python !!!! Got control request: 0x%x", i_query);

	switch (i_query) {
	case ACCESS_CAN_SEEK:
	case ACCESS_CAN_FASTSEEK:
		bp_bool = va_arg(args, bool *);
		*bp_bool = false;
		break;
	case ACCESS_CAN_PAUSE:
		bp_bool = va_arg(args, bool *);
		*bp_bool = true;
		break;
	case ACCESS_CAN_CONTROL_PACE:
		bp_bool = va_arg(args, bool *);
		*bp_bool = true;
		break;
	case ACCESS_GET_PTS_DELAY:
		pi_64 = va_arg(args, int64_t *);
		*pi_64 = DEFAULT_PTS_DELAY;
		break;
	case ACCESS_GET_TITLE_INFO:
	case ACCESS_GET_META:
		return VLC_EGENERIC;
	case ACCESS_SET_PAUSE_STATE:
		bp_bool = va_arg(args, bool *);
		return VLC_SUCCESS;
	default:
		msg_Err(p_access, "Unhandled control request: 0x%x", i_query);
		return VLC_EGENERIC;
	}

	return VLC_SUCCESS;
}

static block_t *
Block(access_t *p_access)
{
	PyObject *result;
	int r;
	block_t *p_block = NULL;
	char *buf;
	Py_ssize_t buf_len;

	if (p_access->p_sys->callback_block) {
		result = PyObject_CallFunction(p_access->p_sys->callback_block, "");

		if (PyErr_Occurred()) {
			p_access->b_die = true;
			PyErr_Print();
			return NULL;
		}

		assert(result);

		if (result == Py_None) {
			p_access->info.b_eof = true;
			p_access->info.i_size = p_access->info.i_pos;
		} else {
			r = PyBytes_AsStringAndSize(result, &buf, &buf_len);
			p_block = block_New(p_access, buf_len);
			memcpy(p_block->p_buffer, buf, buf_len);
			p_access->info.i_pos += p_block->i_buffer;
/*
			msg_Info(p_access, "Pos: %llu", p_access->info.i_pos);
*/
		}

		Py_XDECREF(result);
		return p_block;
	}

	return NULL;
}
