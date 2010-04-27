# -*- coding: utf8 -*-
#
# ***** BEGIN GPL LICENSE BLOCK *****
#
# --------------------------------------------------------------------------
# Blender 2.5 Exporter Framework - LuxRender Plug-in
# --------------------------------------------------------------------------
#
# Authors:
# Doug Hammond, Daniel Genrich
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#
# ***** END GPL LICENCE BLOCK *****
#
# System libs
import os, time, threading

# Framework libs
from ef.ef import ef
from ef.engine import engine_base

# Exporter libs
from .module import LuxManager as LM
from .module import LuxLog
import luxrender.ui.materials
import luxrender.ui.textures
import luxrender.ui.render_panels
import luxrender.ui.camera
import luxrender.ui.lamps
import luxrender.ui.meshes
#import luxrender.nodes

from .export import film		as export_film
from .export import lights		as export_lights
from .export import materials	as export_materials
from .export import geometry	as export_geometry
from .module.file_api			import Files


# Add standard Blender Interface elements
import properties_render
properties_render.RENDER_PT_render.COMPAT_ENGINES.add('luxrender')
properties_render.RENDER_PT_dimensions.COMPAT_ENGINES.add('luxrender')
properties_render.RENDER_PT_output.COMPAT_ENGINES.add('luxrender')
del properties_render

import properties_material
properties_material.MATERIAL_PT_context_material.COMPAT_ENGINES.add('luxrender')
properties_material.MATERIAL_PT_preview.COMPAT_ENGINES.add('luxrender')
del properties_material

import properties_data_lamp
properties_data_lamp.DATA_PT_context_lamp.COMPAT_ENGINES.add('luxrender')
# properties_data_lamp.DATA_PT_area.COMPAT_ENGINES.add('luxrender')
del properties_data_lamp

import properties_texture
properties_texture.TEXTURE_PT_context_texture.COMPAT_ENGINES.add('luxrender')
# TODO: add the other supported blender textures
properties_texture.TEXTURE_PT_clouds.COMPAT_ENGINES.add('luxrender')
del properties_texture

# compatible() copied from blender repository (netrender)
def compatible(module):
	module = __import__(module)
	for subclass in module.__dict__.values():
		try:	subclass.COMPAT_ENGINES.add('luxrender')
		except:	pass
	del module

compatible("properties_data_mesh")
compatible("properties_data_camera")

class luxrender(engine_base):

	'''
	LuxRender Engine Exporter/Integration class
	'''
	
	bl_label = 'LuxRender'
	bl_preview = False # blender's preview scene is inadequate, needs custom rebuild
	
	LuxManager = None
	render_update_timer = None
	output_file = 'default.png'
	
	# This member is read by the ExporterFramework to set up the UI panels
	interfaces = [
		luxrender.ui.render_panels.engine,
		luxrender.ui.render_panels.sampler,
		luxrender.ui.render_panels.integrator,
		luxrender.ui.render_panels.volume,
		luxrender.ui.render_panels.filter,
		luxrender.ui.render_panels.accelerator,

		# custom object data panels
		luxrender.ui.lamps.lamps,
		luxrender.ui.meshes.meshes,
		
		luxrender.ui.camera.camera,
		luxrender.ui.camera.tonemapping,
		
		luxrender.ui.materials.material_editor,
		luxrender.ui.textures.texture_editor,
		
		#luxrender.nodes.test_node
	]
	
	def update_framebuffer(self, xres, yres, fb):
		'''
		xres		int
		yres		int
		fb			list
		
		Update the current RenderResult with the current render image.
		
		This will be called by the LuxFilmDisplay thread started by LuxManager
		
		TODO: perhaps this class itself is a threaded timer ?
		
		Returns None
		'''
		
		#print('fb len: %i' % len(fb))
		#print('fb max: %i' % max(fb))
		#print('fb min: %i' % min(fb))
		
		result = self.begin_result(0,0,xres,yres)
		# TODO: don't read the file whilst it is still being written..
		# ... however file locking in python seems incomplete/non-portable ?
		if os.path.exists(self.output_file):
			lay = result.layers[0]
			# TODO: use the framebuffer direct from pylux when Blender's API supports it
			lay.load_from_file(self.output_file)
		self.end_result(result)
	
	def render(self, context):
		'''
		scene		bpy.types.scene
		
		Export the given scene to LuxRender.
		Choose from one of several methods depending on what needs to be rendered.
		
		Returns None
		'''
		
		if context.name == 'preview':
			self.render_preview(context)
		else:
			self.render_scene(context)
		
	def render_init(self, scene, api_type):
		
		# force scene update to current rendering frame
		scene.set_frame(scene.frame_current)
		
		if scene.luxrender_engine.threads_auto:
			try:
				import multiprocessing
				threads = multiprocessing.cpu_count()
			except:
				# TODO: when might this fail?
				threads = 4
		else:
			threads = scene.luxrender_engine.threads
		
		# Set up the rendering context
		self.LuxManager = LM(
			scene.name,
			api_type = api_type,
			threads = threads
		)
		LM.SetActive(self.LuxManager)
		
		l = self.LuxManager.lux_context
		
		LXS = scene.luxrender_engine.write_lxs
		LXM = scene.luxrender_engine.write_lxm
		LXO = scene.luxrender_engine.write_lxo
		
		if api_type == 'FILE':
			if LXS or LXM or LXO:
				# TODO: insert an output path here ?
				# TODO: only if the user selects a 'keep files' option
				l.set_filename(
					'default',
					LXS = LXS, 
					LXM = LXM,
					LXO = LXO
				)
			else:
				raise Exception('Nothing to do! Select at least one of LXM/LXS/LXO')
		
		# BEGIN!
		self.update_stats('', 'LuxRender: Parsing Scene')
		
		return l
	
	def render_preview(self, scene):
		
		l = self.render_init(scene, 'API')
		
		# Set up render parameters optimised for preview
		from luxrender.export.preview_scene import preview_scene_setup , preview_scene_lights
		preview_scene_setup(scene, l)
		
		# Set up camera, view and film
		l.lookAt( *export_film.lookAt(scene) )
		l.camera( *scene.camera.data.luxrender_camera.api_output(scene) )
		
		l.worldBegin()
		preview_scene_lights(l)
		# Light source iteration and export goes here.
#		if export_lights.lights(l, scene) == False:
#			LuxLog('Error - No lights in scene.')
#			return
		
		# No materials as we're using API with no files, export
		# is handled in geometry iteration
		
		# Geometry iteration and export goes here.
		export_geometry.write_lxo(self, l, scene, smoothing_enabled=False)
		
		self.render_start(scene)
	
	def render_scene(self, scene):
		
		if scene.luxrender_engine.export_type == 'INT' and not scene.luxrender_engine.write_files:
			api_type = 'API'
			write_files = scene.luxrender_engine.write_files
		else:
			api_type = 'FILE'
			write_files = True
		
		l = self.render_init(scene, api_type)
		
		if (api_type == 'API' and not write_files) or (write_files and scene.luxrender_engine.write_lxs):
			# Set up render engine parameters
			l.sampler(				*scene.luxrender_sampler.api_output()		)
			l.accelerator(			*scene.luxrender_accelerator.api_output()	)
			l.surfaceIntegrator(	*scene.luxrender_integrator.api_output()	)
			l.volumeIntegrator(		*scene.luxrender_volume.api_output()		)
			l.pixelFilter(			*scene.luxrender_filter.api_output()		)
			
			# Set up camera, view and film
			l.lookAt(	*export_film.lookAt(scene)	)
			l.camera(	*scene.camera.data.luxrender_camera.api_output(scene)	)
			l.film(		*export_film.film(scene)	)
			
			
			l.worldBegin()
			
			# Light source iteration and export goes here.
			if export_lights.lights(l, scene) == False:
				LuxLog('Error - No lights in scene.')
				return
		
		if (api_type == 'API' and not write_files) or (write_files and scene.luxrender_engine.write_lxm):
			export_materials.ExportedTextures.clear()
			export_materials.ExportedMaterials.clear()
			export_materials.write_lxm(l, scene)
		
		if (api_type == 'API' and not write_files) or (write_files and scene.luxrender_engine.write_lxo):
			export_geometry.write_lxo(self, l, scene, smoothing_enabled=True)
		
		self.render_start(scene)
		
	def render_start(self, scene):
		# TODO: this will be removed when direct framebuffer
		# access is implemented in Blender
		if os.path.exists(self.output_file):
			# reset output image file and
			os.remove(self.output_file)
		
		internal		= (scene.luxrender_engine.export_type == 'INT')
		write_files		= scene.luxrender_engine.write_files
		render			= scene.luxrender_engine.render
		
		# Handle various option combinations using simplified variable names !
		if internal:
			if write_files:
				if render:
					start_rendering = True
					parse = True
					worldEnd = False
				else:
					start_rendering = False
					parse = False
					worldEnd = False
			else:
				# will always render
				start_rendering = True
				parse = False
				worldEnd = True
		else:
			# external always writes files
			if render:
				start_rendering = True
				parse = False
				worldEnd = False
			else:
				start_rendering = False
				parse = False
				worldEnd = False
		
		#print('internal %s' % internal)
		#print('write_files %s' % write_files)
		#print('render %s' % render)
		#print('start_rendering %s' % start_rendering)
		#print('parse %s' % parse)
		#print('worldEnd %s' % worldEnd)
		
		if self.LuxManager.lux_context.API_TYPE == 'FILE':
			#print('calling pylux.context.worldEnd() (1)')
			self.LuxManager.lux_context.worldEnd()
			if parse:
				#print('calling file_api.parse()')
				self.LuxManager.lux_context.parse(self.LuxManager.lux_context.file_names[0], True)
		elif worldEnd:
			#print('calling pylux.context.worldEnd() (2)')
			self.LuxManager.lux_context.worldEnd()
		
		# Begin rendering
		if start_rendering:
			if internal:
				self.LuxManager.start(self)
				self.update_stats('', 'LuxRender: Rendering warmup')
				while self.LuxManager.started:
					self.render_update_timer = threading.Timer(1, self.stats_timer)
					self.render_update_timer.start()
					if self.render_update_timer.isAlive(): self.render_update_timer.join()
			else:
				LuxLog('External LuxRender will be started with scene file "%s"' % self.LuxManager.lux_context.file_names[0])
		
		# TODO: tidy up scene files and output file ?
	
	def stats_timer(self):
		'''
		Update the displayed rendering statistics and detect end of rendering
		
		Returns None
		'''
		
		self.update_stats('', 'LuxRender: Rendering %s' % self.LuxManager.stats_thread.stats_string)
		if self.test_break() or \
			self.LuxManager.lux_context.statistics('filmIsReady') == 1.0 or \
			self.LuxManager.lux_context.statistics('terminated') == 1.0 or \
			self.LuxManager.lux_context.statistics('enoughSamples') == 1.0:
			self.LuxManager.reset()
			LM.ClearActive()
			self.update_stats('', '')
