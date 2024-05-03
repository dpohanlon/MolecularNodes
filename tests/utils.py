import bpy
import molecularnodes as mn
import numpy as np
import random

from syrupy.extensions.amber import AmberSnapshotExtension


# we create a custom snapshot comparison class, which can handle numpy arrays
# and compare them properly. The class will serialize the numpy arrays into lists
# and when comparing them, reads the list back into a numpy array for comparison
# it checks for 'isclose' for floats and otherwise looks for absolute comparison
class NumpySnapshotExtension(AmberSnapshotExtension):
    def serialize(self, data):
        if isinstance(data, np.ndarray):
            return data.tolist()
        return super().serialize(data)

    def assert_match(self, snapshot, test_value):
        if isinstance(test_value, np.ndarray) and isinstance(snapshot, list):
            # if the values are floats, then we use a rough "isclose" to compare them
            # which helps with floating point issues. Between platforms geometry nodes
            # outputs some differences in the meshes which are usually off by ~0.01 or so
            if np.issubdtype(test_value, float):
                assert np.allclose(
                    test_value, np.array(snapshot), rtol=0.05
                ).all()
            else:
                assert (test_value == np.array(snapshot)).all()

        else:
            super().assert_match(snapshot, test_value)


def apply_mods(obj):
    """
    Applies the modifiers on the modifier stack

    This will realise the computations inside of any Geometry Nodes modifiers, ensuring
    that the result of the node trees can be compared by looking at the resulting 
    vertices of the object.
    """
    bpy.context.view_layer.objects.active = obj
    for modifier in obj.modifiers:
        bpy.ops.object.modifier_apply(modifier=modifier.name)


def sample_attribute(object,
                     attribute,
                     n=100,
                     evaluate=True,
                     error: bool = False,
                     seed=6):
    if isinstance(object, mn.io.parse.molecule.Molecule):
        object = object.object

    random.seed(seed)
    if error:
        attribute = mn.blender.obj.get_attribute(
            object, attribute, evaluate=evaluate)
        length = len(attribute)

        if n > length:
            idx = range(length)
        else:
            idx = random.sample(range(length), n)

        if len(attribute.data.shape) == 1:
            return attribute[idx]

        return attribute[idx, :]
    else:
        try:
            attribute = mn.blender.obj.get_attribute(
                object=object,
                name=attribute,
                evaluate=evaluate
            )
            length = len(attribute)

            if n > length:
                idx = range(length)
            else:
                idx = random.sample(range(length), n)

            if len(attribute.data.shape) == 1:
                return attribute[idx]

            return attribute[idx, :]
        except AttributeError as e:
            return np.array(e)


def sample_attribute_to_string(object,
                               attribute,
                               n=100,
                               evaluate=True,
                               precision=3,
                               seed=6):
    if isinstance(object, mn.io.parse.molecule.Molecule):
        object = object.object
    try:
        array = sample_attribute(
            object, attribute=attribute, n=n, evaluate=evaluate, seed=seed)
    except AttributeError as e:
        print(
            f"Error {e}, unable to sample attribute {attribute} from {object}"
        )
        return str(e)

    if array.dtype != bool:
        array = np.round(array, precision)
    length = len(array)
    threshold = 4 * length

    if n > length:
        idx = range(length)
    else:
        idx = random.sample(range(length), n)

    dimensions = len(np.shape(attribute))

    if dimensions == 1:
        array = attribute[idx]
    elif dimensions == 2:
        array = attribute[idx, :]

    return np.array2string(array, precision=precision, threshold=threshold)


def get_verts(obj, float_decimals=4, n_verts=100, apply_modifiers=True, seed=42):
    """
    Randomly samples a specified number of vertices from an object.

    Parameters
    ----------
    obj : object
        Object from which to sample vertices.
    float_decimals : int, optional
        Number of decimal places to round the vertex coordinates, defaults to 4.
    n_verts : int, optional
        Number of vertices to sample, defaults to 100.
    apply_modifiers : bool, optional
        Whether to apply all modifiers on the object before sampling vertices, defaults to True.
    seed : int, optional
        Seed for the random number generator, defaults to 42.

    Returns
    -------
    str
        String representation of the randomly selected vertices.

    Notes
    -----
    This function randomly samples a specified number of vertices from the given object.
    By default, it applies all modifiers on the object before sampling vertices. The
    random seed can be set externally for reproducibility.

    If the number of vertices to sample (`n_verts`) exceeds the number of vertices
    available in the object, all available vertices will be sampled.

    The vertex coordinates are rounded to the specified number of decimal places
    (`float_decimals`) before being included in the output string.

    Examples
    --------
    >>> obj = mn.io.fetch.('6n2y', style='cartoon')
    >>> get_verts(obj, float_decimals=3, n_verts=50, apply_modifiers=True, seed=42)
    '1.234,2.345,3.456\n4.567,5.678,6.789\n...'
    """

    import random

    random.seed(seed)

    if apply_modifiers:
        try:
            apply_mods(obj)
        except RuntimeError as ex:
            return str(ex)

    vert_list = [(v.co.x, v.co.y, v.co.z) for v in obj.data.vertices]

    if n_verts > len(vert_list):
        n_verts = len(vert_list)

    random_verts = random.sample(vert_list, n_verts)

    verts_string = ""
    for i, vert in enumerate(random_verts):
        if i < n_verts:
            rounded = [round(x, float_decimals) for x in vert]
            verts_string += "{},{},{}\n".format(
                rounded[0], rounded[1], rounded[2])

    return verts_string


def remove_all_molecule_objects(mda_session):
    for object in bpy.data.objects:
        try:
            obj_type = object["type"]
            if obj_type == "molecule":
                bpy.data.objects.remove(object)
        except KeyError:
            pass
    # remove frame change
    bpy.context.scene.frame_set(0)

    mda_session.universe_reps = {}
    mda_session.atom_reps = {}
    mda_session.rep_names = []
