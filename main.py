from obllomov.services.obllomov import ObLLoMov
from obllomov.shared.log import logger



logger.info("Init model")
model = ObLLoMov()

scene = model.get_empty_scene()


logger.info("Start generating")
model.generate_scene(scene, "A lightful living room, small bedroom and tiny kitchen", "/Users/terbium/VSCodeProjects/AInterior/AInterior/scenes")
