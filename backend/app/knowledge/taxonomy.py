from dataclasses import dataclass


@dataclass(frozen=True)
class TaxonomyNode:
    id: str
    name: str
    level: str
    parent_id: str | None = None


class Taxonomy:
    """Immutable controlled taxonomy with validated parent/child relationships."""

    VALID_LEVELS = {"subject", "chapter", "topic", "subtopic"}

    def __init__(self, nodes: list[TaxonomyNode]) -> None:
        self._nodes: dict[str, TaxonomyNode] = {}
        for node in nodes:
            if not node.id or node.id in self._nodes:
                raise ValueError(f"Duplicate or empty taxonomy node id: {node.id!r}")
            if not node.name.strip():
                raise ValueError(f"Taxonomy node {node.id!r} has an empty name")
            if node.level not in self.VALID_LEVELS:
                raise ValueError(f"Taxonomy node {node.id!r} has invalid level {node.level!r}")
            if node.parent_id == node.id:
                raise ValueError(f"Taxonomy node {node.id!r} cannot parent itself")
            self._nodes[node.id] = node

        for node in self._nodes.values():
            if node.parent_id is not None and node.parent_id not in self._nodes:
                raise ValueError(
                    f"Taxonomy node {node.id!r} references missing parent {node.parent_id!r}"
                )

        # Detect cycles before validating level relationships so malformed cyclic
        # graphs report their structural root cause deterministically.
        for node_id in self._nodes:
            self._validate_acyclic(node_id)

        for node in self._nodes.values():
            if node.parent_id is None and node.level != "subject":
                raise ValueError(
                    f"Non-subject taxonomy node {node.id!r} must have a parent"
                )
            if node.parent_id is not None:
                parent = self._nodes[node.parent_id]
                expected_parent = {
                    "chapter": "subject",
                    "topic": "chapter",
                    "subtopic": "topic",
                }.get(node.level)
                if parent.level != expected_parent:
                    raise ValueError(
                        f"Taxonomy node {node.id!r} at level {node.level!r} "
                        f"must have a {expected_parent!r} parent"
                    )

    def _validate_acyclic(self, node_id: str) -> None:
        seen: set[str] = set()
        current = self._nodes[node_id]
        while current.parent_id is not None:
            if current.id in seen:
                raise ValueError(f"Taxonomy cycle detected at {current.id!r}")
            seen.add(current.id)
            current = self._nodes[current.parent_id]

    def get(self, node_id: str) -> TaxonomyNode | None:
        return self._nodes.get(node_id)

    def require(self, node_id: str) -> TaxonomyNode:
        node = self.get(node_id)
        if node is None:
            raise KeyError(node_id)
        return node

    def children(self, parent_id: str | None) -> list[TaxonomyNode]:
        return sorted(
            (node for node in self._nodes.values() if node.parent_id == parent_id),
            key=lambda node: (node.name.casefold(), node.id),
        )

    def all(self) -> list[TaxonomyNode]:
        level_order = {"subject": 0, "chapter": 1, "topic": 2, "subtopic": 3}
        return sorted(
            self._nodes.values(),
            key=lambda node: (
                level_order[node.level],
                node.parent_id or "",
                node.name.casefold(),
                node.id,
            ),
        )

    def resolve_path(self, node_id: str) -> list[TaxonomyNode]:
        current = self.require(node_id)
        path: list[TaxonomyNode] = []
        seen: set[str] = set()
        while current is not None:
            if current.id in seen:
                raise ValueError(f"Taxonomy cycle detected at {current.id!r}")
            seen.add(current.id)
            path.append(current)
            current = self.get(current.parent_id) if current.parent_id else None
        return list(reversed(path))

    def descendant_ids(self, node_id: str, include_self: bool = True) -> list[str]:
        """Return a deterministic subtree for hierarchical filtering."""
        self.require(node_id)
        descendants = [
            node.id
            for node in self._nodes.values()
            if node.id == node_id or self._is_descendant(node.id, node_id)
        ]
        if not include_self:
            descendants = [item for item in descendants if item != node_id]
        return sorted(descendants)

    def _is_descendant(self, node_id: str, ancestor_id: str) -> bool:
        current = self._nodes[node_id]
        seen: set[str] = set()
        while current.parent_id is not None:
            if current.id in seen:
                raise ValueError(f"Taxonomy cycle detected at {current.id!r}")
            seen.add(current.id)
            if current.parent_id == ancestor_id:
                return True
            current = self._nodes[current.parent_id]
        return False

    def path_ids(self, node_id: str) -> list[str]:
        return [node.id for node in self.resolve_path(node_id)]


def _chapter(
    subject_id: str,
    number: int,
    name: str,
    topics: tuple[str, ...],
) -> tuple[str, str, tuple[str, ...]]:
    return (f"{subject_id}.c{number:02d}", name, topics)


def _build_default_taxonomy() -> Taxonomy:
    subjects = (
        ("physics", "Physics"),
        ("chemistry", "Chemistry"),
        ("mathematics", "Mathematics"),
    )

    chapters: dict[str, tuple[tuple[str, str, tuple[str, ...]], ...]] = {
        "mathematics": (
            _chapter("mathematics", 1, "Sets, Relations and Functions", ("Sets", "Relations", "Functions", "Composition of functions")),
            _chapter("mathematics", 2, "Complex Numbers and Quadratic Equations", ("Complex numbers", "Argand diagram", "Quadratic equations", "Roots and coefficients")),
            _chapter("mathematics", 3, "Matrices and Determinants", ("Matrices", "Determinants", "Adjoint and inverse", "Linear equations and consistency")),
            _chapter("mathematics", 4, "Permutations and Combinations", ("Counting principle", "Permutations", "Combinations")),
            _chapter("mathematics", 5, "Binomial Theorem and its Simple Applications", ("Binomial theorem", "General and middle terms", "Simple applications")),
            _chapter("mathematics", 6, "Sequence and Series", ("Arithmetic progression", "Geometric progression", "Means and AM-GM relation")),
            _chapter("mathematics", 7, "Limit, Continuity and Differentiability", ("Functions and graphs", "Limits", "Continuity", "Differentiation", "Applications of derivatives")),
            _chapter("mathematics", 8, "Integral Calculus", ("Antiderivatives", "Indefinite integration", "Definite integration", "Fundamental theorem", "Areas under curves")),
            _chapter("mathematics", 9, "Differential Equations", ("Order and degree", "Separation of variables", "Homogeneous equations", "Linear differential equations")),
            _chapter("mathematics", 10, "Coordinate Geometry", ("Cartesian coordinates", "Straight lines", "Circles", "Parabola", "Ellipse and hyperbola")),
            _chapter("mathematics", 11, "Three Dimensional Geometry", ("Coordinates in space", "Direction ratios and cosines", "Lines in space", "Skew lines and shortest distance")),
            _chapter("mathematics", 12, "Vector Algebra", ("Vectors and scalars", "Vector components", "Addition of vectors", "Scalar product", "Vector product")),
            _chapter("mathematics", 13, "Statistics and Probability", ("Measures of dispersion", "Mean, median and mode", "Variance and standard deviation", "Probability theorems", "Bayes theorem", "Random variables")),
            _chapter("mathematics", 14, "Trigonometry", ("Trigonometric identities", "Trigonometric functions", "Inverse trigonometric functions")),
        ),
        "physics": (
            _chapter("physics", 1, "Units and Measurements", ("SI units", "Least count", "Significant figures", "Errors", "Dimensions and dimensional analysis")),
            _chapter("physics", 2, "Kinematics", ("Frame of reference", "Motion in a straight line", "Graphs and equations of motion", "Relative velocity", "Projectile motion", "Uniform circular motion")),
            _chapter("physics", 3, "Laws of Motion", ("Newton's laws", "Momentum and impulse", "Conservation of momentum", "Friction", "Circular motion and centripetal force")),
            _chapter("physics", 4, "Work, Energy and Power", ("Work", "Kinetic and potential energy", "Work-energy theorem", "Power", "Conservation of mechanical energy", "Collisions")),
            _chapter("physics", 5, "Rotational Motion", ("Centre of mass", "Torque and angular momentum", "Moment of inertia", "Parallel and perpendicular axes", "Rigid body equilibrium", "Rotational dynamics")),
            _chapter("physics", 6, "Gravitation", ("Universal gravitation", "Variation of g", "Kepler's laws", "Gravitational potential and energy", "Escape velocity", "Satellites")),
            _chapter("physics", 7, "Properties of Solids and Liquids", ("Elasticity", "Fluid pressure and viscosity", "Bernoulli principle", "Surface tension", "Heat and temperature", "Calorimetry and heat transfer")),
            _chapter("physics", 8, "Thermodynamics", ("Thermal equilibrium", "Zeroth law", "First law", "Isothermal and adiabatic processes", "Second law")),
            _chapter("physics", 9, "Kinetic Theory of Gases", ("Ideal gas equation", "Kinetic interpretation of pressure and temperature", "RMS speed", "Degrees of freedom", "Equipartition", "Mean free path")),
            _chapter("physics", 10, "Oscillations and Waves", ("Periodic motion", "Simple harmonic motion", "Spring and pendulum", "Wave motion", "Standing waves", "Beats")),
            _chapter("physics", 11, "Electrostatics", ("Electric charge and Coulomb law", "Electric field", "Electric dipole", "Electric flux and Gauss law", "Potential and potential energy", "Capacitors")),
            _chapter("physics", 12, "Current Electricity", ("Drift velocity", "Ohm law and resistance", "Electrical power", "Cells and internal resistance", "Kirchhoff laws", "Wheatstone and metre bridge")),
            _chapter("physics", 13, "Magnetic Effects of Current and Magnetism", ("Biot-Savart law", "Ampere law", "Lorentz force", "Force on current-carrying conductor", "Galvanometer", "Magnetic dipoles and materials")),
            _chapter("physics", 14, "Electromagnetic Induction and Alternating Currents", ("Faraday law", "Lenz law", "Self and mutual inductance", "AC values and impedance", "LCR resonance", "Generator and transformer")),
            _chapter("physics", 15, "Electromagnetic Waves", ("Displacement current", "Electromagnetic wave properties", "Transverse nature", "Electromagnetic spectrum", "Applications")),
            _chapter("physics", 16, "Optics", ("Ray optics", "Mirrors and lenses", "Refraction and total internal reflection", "Prism and optical instruments", "Wavefront and Huygens principle", "Interference", "Diffraction", "Polarization")),
            _chapter("physics", 17, "Dual Nature of Matter and Radiation", ("Dual nature of radiation", "Photoelectric effect", "Einstein equation", "Matter waves", "de Broglie relation")),
            _chapter("physics", 18, "Atoms and Nuclei", ("Rutherford model", "Bohr model", "Hydrogen spectrum", "Nuclear composition", "Mass defect and binding energy", "Fission and fusion")),
            _chapter("physics", 19, "Electronic Devices", ("Semiconductors", "Diode characteristics", "Rectifiers", "LED and photodiode", "Solar cell", "Zener diode", "Logic gates")),
            _chapter("physics", 20, "Experimental Skills", ("Vernier calipers", "Screw gauge", "Pendulum", "Young's modulus", "Surface tension and viscosity", "Resonance tube", "Electrical measurements", "Optical measurements", "Diode characteristics")),
        ),
        "chemistry": (
            _chapter("chemistry", 1, "Some Basic Concepts in Chemistry", ("Matter and atomic theory", "Mole concept", "Atomic and molecular masses", "Stoichiometry", "Empirical and molecular formulae")),
            _chapter("chemistry", 2, "Atomic Structure", ("Electromagnetic radiation", "Bohr model", "Dual nature and de Broglie relation", "Quantum numbers", "Atomic orbitals", "Electronic configuration")),
            _chapter("chemistry", 3, "Chemical Bonding and Molecular Structure", ("Ionic bonding", "Covalent bonding", "Electronegativity and Fajan rule", "VSEPR", "Hybridization", "Molecular orbital theory", "Hydrogen bonding")),
            _chapter("chemistry", 4, "Chemical Thermodynamics", ("System and surroundings", "First law", "Enthalpy and Hess law", "Entropy", "Gibbs energy and spontaneity")),
            _chapter("chemistry", 5, "Solutions", ("Concentration terms", "Raoult law", "Ideal and non-ideal solutions", "Colligative properties", "van't Hoff factor")),
            _chapter("chemistry", 6, "Equilibrium", ("Dynamic equilibrium", "Physical equilibria", "Chemical equilibrium", "Le Chatelier principle", "Ionic equilibrium", "Acids and bases", "pH and buffers", "Solubility product")),
            _chapter("chemistry", 7, "Redox Reactions and Electrochemistry", ("Oxidation and reduction", "Oxidation number", "Redox balancing", "Conductance", "Electrochemical cells", "Nernst equation", "Fuel cells")),
            _chapter("chemistry", 8, "Chemical Kinetics", ("Reaction rate", "Rate law", "Order and molecularity", "Integrated rate equations", "Half-life", "Arrhenius equation", "Activation energy")),
            _chapter("chemistry", 9, "Classification of Elements and Periodicity in Properties", ("Periodic law", "s, p, d and f blocks", "Atomic and ionic radii", "Ionization enthalpy", "Electron gain enthalpy", "Oxidation states and reactivity")),
            _chapter("chemistry", 10, "p-Block Elements", ("Groups 13 to 18", "Electronic configurations", "Periodic trends", "Unique behaviour of first elements")),
            _chapter("chemistry", 11, "d- and f-Block Elements", ("Transition elements", "Electronic configuration", "Oxidation states", "Magnetic and catalytic properties", "Coordination tendency", "Lanthanoids", "Actinoids", "KMnO4 and K2Cr2O7")),
            _chapter("chemistry", 12, "Coordination Compounds", ("Werner theory", "Ligands and coordination number", "Denticity and chelation", "Nomenclature", "Isomerism", "Valence bond approach", "Crystal field basics", "Colour and magnetism")),
            _chapter("chemistry", 13, "Purification and Characterisation of Organic Compounds", ("Crystallization", "Sublimation", "Distillation", "Extraction", "Chromatography", "Qualitative analysis", "Quantitative analysis")),
            _chapter("chemistry", 14, "Some Basic Principles of Organic Chemistry", ("Tetravalency and hybridization", "Functional groups", "Isomerism", "IUPAC nomenclature", "Bond fission", "Reactive intermediates", "Electronic effects", "Organic reaction types")),
            _chapter("chemistry", 15, "Hydrocarbons", ("Alkanes", "Alkenes", "Alkynes", "Aromatic hydrocarbons", "Conformations", "Electrophilic addition", "Ozonolysis", "Electrophilic substitution")),
            _chapter("chemistry", 16, "Organic Compounds Containing Halogens", ("Preparation", "C-X bond", "Substitution mechanisms", "Chloroform", "Iodoform", "Freons and DDT")),
            _chapter("chemistry", 17, "Organic Compounds Containing Oxygen", ("Alcohols", "Phenols", "Ethers", "Aldehydes and ketones", "Grignard reagent", "Oxidation and reduction", "Aldol and Cannizzaro reactions", "Carboxylic acids")),
            _chapter("chemistry", 18, "Organic Compounds Containing Nitrogen", ("Amines", "Preparation and properties", "Basic character", "Identification of amines", "Diazonium salts")),
            _chapter("chemistry", 19, "Biomolecules", ("Carbohydrates", "Proteins", "Amino acids and peptide bonds", "Vitamins", "Nucleic acids", "Hormones")),
            _chapter("chemistry", 20, "Principles Related to Practical Chemistry", ("Functional group tests", "Organic qualitative analysis", "Preparations", "Titrimetric analysis", "Salt analysis", "Practical enthalpy experiments", "Sol preparation", "Kinetic practical")),
        ),
    }

    nodes: list[TaxonomyNode] = [
        TaxonomyNode(subject_id, name, "subject")
        for subject_id, name in subjects
    ]

    for subject_id, subject_chapters in chapters.items():
        for chapter_id, chapter_name, topics in subject_chapters:
            nodes.append(TaxonomyNode(chapter_id, chapter_name, "chapter", subject_id))
            for topic_index, topic_name in enumerate(topics, start=1):
                topic_id = f"{chapter_id}.t{topic_index:02d}"
                nodes.append(TaxonomyNode(topic_id, topic_name, "topic", chapter_id))

    return Taxonomy(nodes)


# Controlled JEE Main 2026 Paper 1 taxonomy.
# Official unit boundaries are represented as chapter nodes; syllabus concepts are
# represented as topic nodes. Subtopic depth remains supported by Taxonomy for
# future syllabus expansion without changing the persistence contract.
DEFAULT_TAXONOMY = _build_default_taxonomy()
