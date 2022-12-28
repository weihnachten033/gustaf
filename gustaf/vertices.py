"""gustaf/gustaf/vertices.py.

Vertices. Base of all "Mesh" geometries.
"""

import copy

import numpy as np

from gustaf import helpers, settings, show, utils
from gustaf._base import GustafBase
from gustaf.helpers.options import Option


class VerticesShowOption(helpers.options.ShowOption):
    """
    Show options for vertices.
    """

    _valid_options = helpers.options.make_valid_options(
        *helpers.options.vedo_common_options,
        Option("vedo", "r", "Radius of vertices in units of pixels.", (int,)),
    )

    _helps = "Vertices"

    def _initialize_vedo_showable(self):
        """
        Initialize Vertices showable for vedo.

        Parameters
        ----------
        None

        Returns
        -------
        vertices: vedo.Points
        """
        init_options = ("r",)

        return show.vedo.Points(
            self._helpee.const_vertices, **self[init_options]
        )


class Vertices(GustafBase):

    kind = "vertex"

    __slots__ = (
        "_vertices",
        "_const_vertices",
        "_computed",
        "_show_options",
        "vertexdata",
    )

    # define freuqently used types as dunder variable
    __show_option__ = VerticesShowOption
    __parent__ = GustafBase

    def __init__(
        self,
        vertices=None,
    ):
        """Vertices. It has vertices.

        Parameters
        -----------
        vertices: (n, d) np.ndarray

        Returns
        --------
        None
        """
        self.vertices = vertices

        self.vertexdata = helpers.data.VertexData(self)

        self._computed = helpers.data.ComputedMeshData(self)
        self._show_options = self.__show_option__(self)

    @property
    def vertices(self):
        """Returns vertices.

        Parameters
        -----------
        None

        Returns
        --------
        vertices: (n, d) np.ndarray
        """
        self._logd("returning vertices")
        return self._vertices

    @vertices.setter
    def vertices(self, vs):
        """Vertices setter. This will saved as a tracked array. This tracked
        array is very sensitive and if we do anything with it that may hint an
        inplace operation, it will be marked as modified. This includes copying
        and slicing. If you know you aren't going to modify the array, please
        consider using `const_vertices`. Somewhat c-style hint in naming.

        Parameters
        -----------
        vs: (n, d) np.ndarray

        Returns
        --------
        None
        """
        self._logd("setting vertices")

        self._vertices = helpers.data.make_tracked_array(
            vs, settings.FLOAT_DTYPE
        )

        # shape check
        utils.arr.is_shape(vs, (-1, -1), strict=True)

        # exact same, but not tracked.
        self._const_vertices = self._vertices.view()
        self._const_vertices.flags.writeable = False

        # at each setting, validate vertexdata
        # --> by len mismatch, will clear data
        if hasattr(self, "vertexdata"):
            self.vertexdata._validate_len(raise_=False)

    @property
    def const_vertices(self):
        """Returns non-mutable view of `vertices`. Naming inspired by c/cpp
        sessions.

        Parameters
        -----------
        None

        Returns
        --------
        None
        """
        self._logd("returning const_vertices")
        return self._const_vertices

    @property
    def show_options(self):
        """
        Returns a show option manager for this object. Behaves similar to
        dict.

        Parameters
        ----------
        None

        Returns
        -------
        show_options: ShowOption
          A derived class that's suitable for current class.
        """
        self._logd("returning show_options")
        return self._show_options

    @property
    def vis_dict(self):
        """
        Temporary backward compatibility
        """
        self._logw("`vis_dict` is deprecated. Please use `show_options`")
        return self.show_options

    @vis_dict.setter
    def vis_dict(self, vd):
        """
        Tmp
        """
        self._logw("`vis_dict` is deprecated. Please use `show_options`")
        self._show_options = vd

    @property
    def whatami(self):
        """Answers deep philosophical question: "what am i"?

        Parameters
        ----------
        None

        Returns
        --------
        whatami: str
          vertices
        """
        return "vertices"

    @helpers.data.ComputedMeshData.depends_on(["vertices"])
    def unique_vertices(self, tolerance=None, **kwargs):
        """Returns a namedtuple that holds unique vertices info. Unique here
        means "close-enough-within-tolerance".

        Parameters
        -----------
        tolerance: float
          (Optional) Default is settings.TOLERANCE
        recompute: bool
          Only applicable as keyword argument. Force re-computes.

        Returns
        --------
        unique_vertices_info: Unique2DFloats
          namedtuple with `values`, `ids`, `inverse`, `intersection`.
        """
        self._logd("computing unique vertices")
        if tolerance is None:
            tolerance = settings.TOLERANCE

        values, ids, inverse, intersection = utils.arr.close_rows(
            self.const_vertices, tolerance=tolerance
        )

        return helpers.data.Unique2DFloats(
            values,
            ids,
            inverse,
            intersection,
        )

    @helpers.data.ComputedMeshData.depends_on(["vertices"])
    def bounds(self):
        """Returns bounds of the vertices. Bounds means AABB of the geometry.

        Parameters
        -----------
        None

        Returns
        --------
        bounds: (d,) np.ndarray
        """
        self._logd("computing bounds")
        return utils.arr.bounds(self.const_vertices)

    @helpers.data.ComputedMeshData.depends_on(["vertices"])
    def bounds_diagonal(self):
        """Returns diagonal vector of the bounding box.

        Parameters
        -----------
        None

        Returns
        --------
        bounds_digonal: (d,) np.ndarray
          same as `bounds[1] - bounds[0]`
        """
        self._logd("computing bounds_diagonal")
        bounds = self.bounds()
        return bounds[1] - bounds[0]

    @helpers.data.ComputedMeshData.depends_on(["vertices"])
    def bounds_diagonal_norm(self):
        """Returns norm of bounds diagonal.

        Parameters
        -----------
        None

        Returns
        --------
        bounds_diagonal_norm: float
        """
        self._logd("computing bounds_diagonal_norm")
        return float(sum(self.bounds_diagonal() ** 2) ** 0.5)

    def update_vertices(self, mask, inverse=None):
        """Update vertices with a mask. In other words, keeps only masked
        vertices. Adapted from `github.com/mikedh/trimesh`. Updates
        connectivity accordingly too.

        Parameters
        -----------
        mask: (n,) bool or int
        inverse: (len(self.vertices),) int

        Returns
        --------
        updated_self: type(self)
        """
        vertices = self.const_vertices.copy()

        # make mask numpy array
        mask = np.asarray(mask)

        if (mask.dtype.name == "bool" and mask.all()) or len(mask) == 0:
            return self

        # create inverse mask if not passed
        check_neg = False
        if inverse is None and self.kind != "vertex":
            inverse = np.full(len(vertices), -11, dtype=settings.INT_DTYPE)
            check_neg = True
            if mask.dtype.kind == "b":
                inverse[mask] = np.arange(mask.sum())
            elif mask.dtype.kind == "i":
                inverse[mask] = np.arange(len(mask))
            else:
                inverse = None

        # re-index elements from inverse
        # TODO: Here could be a good place to preserve BCs.
        elements = None
        if inverse is not None and self.kind != "vertex":
            elements = self.const_elements.copy()
            elements = inverse[elements.reshape(-1)].reshape(
                (-1, elements.shape[1])
            )
            # remove all the elements that's not part of inverse
            if check_neg:
                emask = (elements > -1).all(axis=1)
                elements = elements[emask]

        # apply mask
        vertices = vertices[mask]

        def update_vertexdata(obj, m, vertex_data=None):
            """apply mask to vertex data if there's any."""
            newdata = dict()
            if vertex_data is None:
                vertex_data = obj.vertexdata

            for key, values in vertex_data.items():
                newdata[key] = values[m]

            obj.vertexdata = newdata

            return obj

        # update
        self.vertices = vertices
        if elements is not None:
            self.elements = elements

        update_vertexdata(self, mask)

        return self

    def select_vertices(self, ranges):
        """Returns vertices inside the given range.

        Parameters
        -----------
        ranges: (d, 2) array-like
          Takes None.

        Returns
        --------
        ids: (n,) np.ndarray
        """
        return utils.arr.select_with_ranges(self.vertices, ranges)

    def remove_vertices(self, ids):
        """Removes vertices with given vertex ids.

        Parameters
        -----------
        ids: (n,) np.ndarray

        Returns
        --------
        new_self: type(self)
        """
        mask = np.ones(len(self.vertices), dtype=bool)
        mask[ids] = False

        return self.update_vertices(mask)

    def merge_vertices(self, tolerance=None):
        """Based on unique vertices, merge vertices if it is mergeable.

        Parameters
        -----------
        tolerance: float
          Default is settings.TOLERANCE

        Returns
        --------
        merged_self: type(self)
        """
        unique_vs = self.unique_vertices()

        self._logd("number of vertices")
        self._logd(f"  before merge: {len(self.vertices)}")
        self._logd(f"  after merge: {len(unique_vs.ids)}")

        return self.update_vertices(
            mask=unique_vs.ids,
            inverse=unique_vs.inverse,
        )

    def showable(self, **kwargs):
        """Returns showable object, meaning object of visualization backend.

        Parameters
        -----------
        **kwargs:

        Returns
        --------
        showable: obj
          Obj of `gustaf.settings.VISUALIZATION_BACKEND`
        """
        return show.make_showable(self, **kwargs)

    def show(self, **kwargs):
        """Show current object using visualization backend.

        Parameters
        -----------
        **kwargs:


        Returns
        --------
        None
        """
        return show.show(self, **kwargs)

    def copy(self):
        """Returns deepcopy of self.

        Parameters
        -----------
        None

        Returns
        --------
        selfcopy: type(self)
        """
        # all attributes are deepcopy-able
        return copy.deepcopy(self)

    @classmethod
    def concat(cls, *instances):
        """Sequentially put them together to make one object.

        Parameters
        -----------
        *instances: List[type(cls)]
          Allows one iterable object also.

        Returns
        --------
        one_instance: type(cls)
        """

        def is_concatable(inst):
            """Return true, if it is same as type(cls)"""
            if isinstance(inst, cls):
                return True
            else:
                return False

        # If only one instance is given and it is iterable, adjust
        # so that we will just iterate that.
        if (
            len(instances) == 1
            and not isinstance(instances[0], str)
            and hasattr(instances[0], "__iter__")
        ):
            instances = instances[0]

        vertices = []
        haselem = cls.kind != "vertex"
        if haselem:
            elements = []

        # check if everything is "concatable".
        for ins in instances:
            if not is_concatable(ins):
                raise TypeError(
                    "Can't concat. One of the instances is not "
                    f"`{cls.__name__}`."
                )

            # make sure each element index starts from 0 & end at len(vertices)
            tmp_ins = ins.copy().remove_unreferenced_vertices()

            vertices.append(tmp_ins.vertices.copy())

            if haselem:
                if len(elements) == 0:
                    elements.append(tmp_ins.elements.copy())
                    e_offset = elements[-1].max() + 1

                else:
                    elements.append(
                        # copy is not necessary here,
                        tmp_ins.elements
                        + e_offset
                    )
                    e_offset = elements[-1].max() + 1

        if haselem:
            return cls(
                vertices=np.vstack(vertices),
                elements=np.vstack(elements),
            )

        else:
            return Vertices(vertices=np.vstack(vertices))

    def __add__(self, to_add):
        """Concat in form of +.

        Parameters
        -----------
        to_add: type(self)

        Returns
        --------
        added: type(self)
        """
        return type(self).concat(self, to_add)
