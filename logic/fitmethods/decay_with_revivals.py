import numpy as np
from lmfit.models import Model
from core.util.math import compute_ft


def make_cos_square_model(self, prefix=None):

    def cos_square_function(x, f):
        return np.square(np.cos(2 * np.pi * f * x))

    if not isinstance(prefix, str) and prefix is not None:
        self.log.error('The passed prefix <{0}> of type {1} is not a string and'
                       'cannot be used as a prefix and will be ignored for now.'
                       'Correct that!'.format(prefix, type(prefix)))
        model = Model(cos_square_function, independent_vars=['x'])
    else:
        model = Model(cos_square_function, independent_vars=['x'], prefix=prefix)

    params = model.make_params()

    return model, params


def make_stretched_exponential_revivals(self, prefix=None):
        """ Create a model of a cos2 with stretched exponential decay.

        @param str prefix: optional, if multiple models should be used in a
                           composite way and the parameters of each model should be
                           distinguished from each other to prevent name collisions.

        @return tuple: (object model, object params), for more description see in
                       the method make_cos_square_model.
        """

        cos2_model, params = self.make_cos_square_model(prefix=prefix)
        bare_stretched_exp_decay_model, params = self.make_barestretchedexponentialdecay_model(prefix=prefix)
        constant_model, params = self.make_constant_model(prefix=prefix)

        model = cos2_model * bare_stretched_exp_decay_model + constant_model
        params = model.make_params()

        return model, params


def estimate_cos_square(self, x_axis, data, params):
    errors, params = self.estimate_sin_bare(x_axis, data, params)
    params['frequency'].set(params['frequency']*.5)
    params['phase'].set(0)
    params['offset'].set(np.average(data-1))
    return params, errors
