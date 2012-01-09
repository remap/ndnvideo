/*****************************************************************************
 * Preamble
 *****************************************************************************/

#include <Python.h>

#ifdef HAVE_CONFIG_H
#    include "config.h"
#endif

#include <limits.h>

#include <vlc_common.h>
#include <vlc_plugin.h>
#include <vlc_sout.h>
#include <vlc_block.h>

#include "access.h"

#define PYTHON_SCRIPT "access_output.py"

struct sout_access_out_sys_t {
	PyObject *callback_open;
	PyObject *callback_close;
	PyObject *callback_write;
};

static struct sout_access_out_sys_t *g_sys;

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
static ssize_t Write(sout_access_out_t *, block_t *);
static int Seek(sout_access_out_t *, off_t);
static int Control(sout_access_out_t *, int, va_list);

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
	} else if (!strcmp(type, "write")) {
		Py_XDECREF(g_sys->callback_write);
		Py_INCREF(callback);
		g_sys->callback_write = callback;
	} else {
		PyErr_Format(PyExc_ValueError, "invalid type: %s", type);
		return NULL;
	}

	Py_RETURN_NONE;
}

static PyMethodDef AccessMethods[] = {
	{"set_callback", access_set_callback, METH_VARARGS, "Set callbacks for"
		" access output module"},
	{NULL, NULL, 0, NULL}
};

/*****************************************************************************
 * Module descriptor
 *****************************************************************************/

#define SCRIPT_TEXT N_("Script")
#define SCRIPT_LONG_TEXT N_("Python script filename")

vlc_module_begin();

set_shortname(N_("Python_out"));
set_description(N_("Python output"));
set_category(CAT_SOUT);
set_subcategory(SUBCAT_SOUT_ACO);

add_string("python-script", PYTHON_SCRIPT, NULL, SCRIPT_TEXT, SCRIPT_LONG_TEXT,
		false);

/*
change_safe();
 */
set_capability("sout access", 0);
add_shortcut("pyccn_out");
set_callbacks(Open, Close);

vlc_module_end();

/*****************************************************************************
 * Open: initialize interface
 *****************************************************************************/
static int
Open(vlc_object_t *p_this)
{
	sout_access_out_t *p_access = (sout_access_out_t *) p_this;
	FILE *fp;
	PyObject *res;
	int r;

	if (g_sys) {
		msg_Err(p_access, "Only one instance is allowed");
		return VLC_EGENERIC;
	}

	msg_Info(p_this, "!!!! Python !!!! Got open request for name: %s",
			p_access->psz_path);


	p_access->pf_write = Write;
	p_access->pf_seek = Seek;
	p_access->pf_control = Control;

	g_sys = calloc(1, sizeof(struct sout_access_out_sys_t));
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

	msg_Info(p_this, "!!!! Python !!!! Loading script");

	r = PyRun_SimpleFileEx(fp, PYTHON_SCRIPT, false);
	fclose(fp);
	if (r < 0)
		goto error;

	msg_Info(p_this, "!!!! Python !!!! Done");

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
	sout_access_out_t *p_access = (sout_access_out_t *) p_this;

	msg_Info(p_this, "!!!! Python !!!! Got close request");

	if (PyErr_Occurred())
		PyErr_Print();

	Py_Finalize();

	free(p_access->p_sys);
	vlc_object_kill(p_this);
	g_sys = NULL;
}

static PyObject *
make_block_entry(block_t *p_buffer_chain)
{
	PyObject *py_flags = NULL, *py_pts = NULL, *py_dts = NULL,
			*py_length = NULL, *py_block = NULL;
	PyObject *result = NULL;

	py_block = PyBytes_FromStringAndSize((char *) p_buffer_chain->p_buffer,
			p_buffer_chain->i_buffer);
	JUMP_IF_NULL(py_block, exit);

	py_flags = PyLong_FromLong(p_buffer_chain->i_flags);
	JUMP_IF_NULL(py_flags, exit);

	py_pts = PyLong_FromLongLong(p_buffer_chain->i_pts);
	JUMP_IF_NULL(py_pts, exit);

	py_dts = PyLong_FromLongLong(p_buffer_chain->i_dts);
	JUMP_IF_NULL(py_dts, exit);

	py_length = PyLong_FromLongLong(p_buffer_chain->i_length);
	JUMP_IF_NULL(py_length, exit);


	result = PyTuple_Pack(5, py_block, py_flags, py_pts, py_dts, py_length);

exit:
	Py_XDECREF(py_length);
	Py_XDECREF(py_dts);
	Py_XDECREF(py_pts);
	Py_XDECREF(py_flags);
	Py_XDECREF(py_block);

	return result;
}

static ssize_t
Write(sout_access_out_t *p_access, block_t *p_buffer_chain)
{
	size_t i_write = 0;
	PyObject *py_list = NULL, *py_block, *py_result;
	block_t *b;
	int r;
	Py_ssize_t res_amount;

	if (p_access->p_sys->callback_write) {
		py_list = PyList_New(0);
		JUMP_IF_NULL(py_list, error);

		b = p_buffer_chain;
		while (b) {
			py_block = make_block_entry(b);

			r = PyList_Append(py_list, py_block);
			Py_DECREF(py_block);
			JUMP_IF_NEG(r, error);

			b = b->p_next;
		}

		block_ChainRelease(p_buffer_chain);

		py_result = PyObject_CallFunctionObjArgs(p_access->p_sys->callback_write,
				py_list, NULL);
		Py_CLEAR(py_list);
		JUMP_IF_NULL(py_result, error);

		if (py_result == Py_None) {
/*
			p_access->b_die = true;
*/
			res_amount = 0;
		} else
			res_amount = PyLong_AsSsize_t(py_result);
		Py_DECREF(py_result);
		JUMP_IF_ERR(error);

		i_write += res_amount;
	}

	return i_write;

error:
	PyErr_Print();
	p_access->b_die = true;
	Py_XDECREF(py_list);
	return 0;
}

static int
Seek(sout_access_out_t *p_access, off_t i_pos)
{
	return 0;
}

static int
Control(sout_access_out_t *p_access, int i_query, va_list args)
{
	bool *bp_bool;
	int64_t *pi_64;

	msg_Info(p_access, "!!!! Python !!!! Got control request: 0x%x", i_query);

	switch (i_query) {
	case ACCESS_OUT_CONTROLS_PACE:
		bp_bool = va_arg(args, bool *);
		*bp_bool = true;
		break;
	default:
		msg_Err(p_access, "Unhandled control request: 0x%x", i_query);
		return VLC_EGENERIC;
	}

	return VLC_SUCCESS;
}