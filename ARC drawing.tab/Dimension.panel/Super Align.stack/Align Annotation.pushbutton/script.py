# -*- coding: utf-8 -*-
import sys
import os
import datetime
from Autodesk.Revit.DB import XYZ, Transaction, TransactionGroup, ElementTransformUtils, TextNote, IndependentTag, Dimension, ModelCurve, DetailCurve, Plane, SketchPlane, AnnotationSymbol
from Autodesk.Revit.DB.Architecture import RoomTag
from pyrevit.forms import select_views, select_sheets
from pyrevit import forms
from pyrevit import revit, DB, UI
from Autodesk.Revit.UI.Selection import ObjectType 
from System.Collections.Generic import List
from System.Windows.Forms import MessageBox
import Autodesk

__doc__ = 'Công cụ căn chỉnh các annotation (Text Notes, Room Tags, Tags, Multi-Category Tags, Wall Tags, Structural Framing Tags, Structural Foundation Tags, Structural Column Tags, Floor Tags, Door Tags, Window Tags, Generic Annotations, Dimensions, Lines, Generic Model Tags, Casework Tags, Detail Item Tags) theo đối tượng chuẩn.'
__title__ = 'Align Annotation'

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document
view = doc.ActiveView

# Hàm set work plane
def set_work_plane_for_view(view):
	try:
		if view.SketchPlane:
			current_plane = view.SketchPlane.GetPlane()
			if current_plane.Normal.IsAlmostEqualTo(view.ViewDirection) and current_plane.Origin.IsAlmostEqualTo(view.Origin):
				return True
		plane = Plane.CreateByNormalAndOrigin(view.ViewDirection, view.Origin)
		sketch_plane = SketchPlane.Create(doc, plane)
		view.SketchPlane = sketch_plane
		return True
	except:
		return False

pre_selected_ids = uidoc.Selection.GetElementIds()

if pre_selected_ids.Count == 1:
	reference_id = pre_selected_ids[0]
	reference_ele = doc.GetElement(reference_id)
else:
	try:
		with forms.WarningBar(title="Chọn một đối tượng làm chuẩn (bấm ESC để thoát)"):
			selected_id = uidoc.Selection.PickObject(ObjectType.Element, "Chọn một đối tượng làm chuẩn")
		reference_ele = doc.GetElement(selected_id)
	except:
		sys.exit()

category = reference_ele.Category.Name

def move_element(idoc, element, vector):
	try:
		if not vector.IsZeroLength():
			ElementTransformUtils.MoveElement(idoc, element.Id, vector)
	except Exception as e:
		# Silently skip to avoid breaking transaction
		return

tg = TransactionGroup(doc, "Align Annotation")
try:
	tg.Start()

	t_set_plane = Transaction(doc, "Set Work Plane")
	t_set_plane.Start()
	if not set_work_plane_for_view(view):
		raise Exception("Failed to set work plane")
	t_set_plane.Commit()

	if category == "Text Notes":
		def tinh_toan_phuong_align(point1, point2):
			vector = XYZ(point1.X-point2.X, point1.Y-point2.Y, point1.Z-point2.Z)
			if abs(vector.X) < abs(vector.Y):
				new_point = XYZ(point1.X, point2.Y, point2.Z)
			else:
				new_point = XYZ(point2.X, point1.Y, point2.Z)
			return new_point
		
		class FamilyTagSelectionFilter(Autodesk.Revit.UI.Selection.ISelectionFilter):
			def AllowElement(self, element):
				return isinstance(element, TextNote)
		
		def pick_text_notes():
			selected_elements = []
			reference_position = reference_ele.Coord
			first_prompt = "Click để chọn một Text Note để align (ESC để chuyển sang quét chuột)"
			subsequent_prompt = "Click để chọn thêm Text Note để align (ESC để chuyển sang quét chuột)"
			rectangle_first_prompt = "Quét chuột để chọn Text Notes (ESC để thoát)"
			rectangle_subsequent_prompt = "Quét chuột để chọn thêm Text Notes (ESC để thoát)"
			
			t = Transaction(doc, "Align Text Notes")
			t.Start()
			try:
				with forms.WarningBar(title=first_prompt):
					while True:
						try:
							prompt = first_prompt if not selected_elements else subsequent_prompt
							with forms.WarningBar(title=prompt):
								elem = uidoc.Selection.PickObject(
									ObjectType.Element,
									FamilyTagSelectionFilter(),
									prompt
								)
							target_ele = doc.GetElement(elem.ElementId)
							target_position = target_ele.Coord
							move_point = tinh_toan_phuong_align(reference_position, target_position)
							target_ele.Coord = move_point
							selected_elements.append(target_ele)
						except Autodesk.Revit.Exceptions.OperationCanceledException:
							break
			finally:
				t.Commit()
			
			if not selected_elements:
				while True:
					try:
						prompt = rectangle_first_prompt if not selected_elements else rectangle_subsequent_prompt
						with forms.WarningBar(title=prompt):
							new_elements = uidoc.Selection.PickElementsByRectangle(
								FamilyTagSelectionFilter(),
								"Chọn Text Notes"
							)
						if new_elements:
							t = Transaction(doc, "Align Text Notes")
							t.Start()
							try:
								for target_ele in new_elements:
									if target_ele.Id not in [e.Id for e in selected_elements]:
										target_position = target_ele.Coord
										move_point = tinh_toan_phuong_align(reference_position, target_position)
										target_ele.Coord = move_point
										selected_elements.append(target_ele)
							finally:
								t.Commit()
						else:
							break
					except Autodesk.Revit.Exceptions.OperationCanceledException:
						break
			
			return selected_elements
		
		def main():
			pick_text_notes()

		main()

	elif category == "Room Tags":
		def tinh_toan_phuong_align(reference_point, target_point):
			try:
				if reference_point is None or target_point is None:
					return XYZ(0, 0, 0)
				
				vector = XYZ(reference_point.X - target_point.X, 
						   reference_point.Y - target_point.Y, 
						   reference_point.Z - target_point.Z)
				
				if view.ViewType in [DB.ViewType.FloorPlan, DB.ViewType.CeilingPlan, DB.ViewType.EngineeringPlan]:
					if abs(vector.Y) > abs(vector.X):
						new_point = XYZ(reference_point.X, target_point.Y, target_point.Z)
					else:
						new_point = XYZ(target_point.X, reference_point.Y, target_point.Z)
					move_vector = XYZ(new_point.X - target_point.X, 
									new_point.Y - target_point.Y, 
									new_point.Z - target_point.Z)
				elif view.ViewType == DB.ViewType.Section:
					right_dir = view.RightDirection
					# Check if section is parallel to Y-axis (RightDirection ≈ (0, ±1, 0))
					if abs(right_dir.Y) > 0.99 and abs(right_dir.X) < 0.01 and abs(right_dir.Z) < 0.01:
						y_diff = abs(reference_point.Y - target_point.Y)
						z_diff = abs(reference_point.Z - target_point.Z)
						if y_diff < z_diff:
							# Align along Y
							new_point = XYZ(target_point.X, reference_point.Y, target_point.Z)
						else:
							# Align along Z
							new_point = XYZ(target_point.X, target_point.Y, reference_point.Z)
					# Check if section is parallel to X-axis (RightDirection ≈ (±1, 0, 0))
					elif abs(right_dir.X) > 0.99 and abs(right_dir.Y) < 0.01 and abs(right_dir.Z) < 0.01:
						x_diff = abs(reference_point.X - target_point.X)
						z_diff = abs(reference_point.Z - target_point.Z)
						if x_diff < z_diff:
							# Align along X
							new_point = XYZ(reference_point.X, target_point.Y, target_point.Z)
						else:
							# Align along Z
							new_point = XYZ(target_point.X, target_point.Y, reference_point.Z)
					else:
						# Default to Z alignment for other section orientations
						new_point = XYZ(target_point.X, target_point.Y, reference_point.Z)
					move_vector = XYZ(new_point.X - target_point.X, 
									new_point.Y - target_point.Y, 
									new_point.Z - target_point.Z)
				else:
					move_vector = XYZ(0, 0, 0)
				return move_vector
			except:
				return XYZ(0, 0, 0)
		
		class RoomTagSelectionFilter(Autodesk.Revit.UI.Selection.ISelectionFilter):
			def AllowElement(self, element):
				return isinstance(element, RoomTag)
		
		def pick_room_tags():
			selected_elements = []
			try:
				reference_point = None
				try:
					if reference_ele.Location:
						reference_point = reference_ele.Location.Point
					else:
						try:
							bbox = reference_ele.get_BoundingBox(view)
							if bbox:
								reference_point = (bbox.Min + bbox.Max) / 2
						except:
							pass
				except:
					pass
				
				if reference_point is None:
					return selected_elements
				
				first_prompt = "Click để chọn một Room Tag để align (ESC để chuyển sang quét chuột)"
				subsequent_prompt = "Click để chọn thêm Room Tag để align (ESC để chuyển sang quét chuột)"
				rectangle_first_prompt = "Quét chuột để chọn Room Tags (ESC để thoát)"
				rectangle_subsequent_prompt = "Quét chuột để chọn thêm Room Tags (ESC để thoát)"
				
				t = Transaction(doc, "Align Room Tags")
				t.Start()
				try:
					with forms.WarningBar(title=first_prompt):
						while True:
							try:
								prompt = first_prompt if not selected_elements else subsequent_prompt
								with forms.WarningBar(title=prompt):
									elem = uidoc.Selection.PickObject(
										ObjectType.Element,
										RoomTagSelectionFilter(),
										prompt
									)
								target_ele = doc.GetElement(elem.ElementId)
								if not target_ele.IsValidObject:
									continue
								
								target_point = None
								try:
									if target_ele.Location:
										target_point = target_ele.Location.Point
									else:
										try:
											bbox = target_ele.get_BoundingBox(view)
											if bbox:
												target_point = (bbox.Min + bbox.Max) / 2
										except:
											continue
								except:
									continue
								
								vector_move = tinh_toan_phuong_align(reference_point, target_point)
								move_element(doc, target_ele, vector_move)
								selected_elements.append(target_ele)
							except Autodesk.Revit.Exceptions.OperationCanceledException:
								break
							except:
								continue
				finally:
					t.Commit()
				
				if not selected_elements:
					while True:
						try:
							prompt = rectangle_first_prompt if not selected_elements else rectangle_subsequent_prompt
							with forms.WarningBar(title=prompt):
								new_elements = uidoc.Selection.PickElementsByRectangle(
									RoomTagSelectionFilter(),
									"Chọn Room Tags"
								)
							if new_elements:
								t = Transaction(doc, "Align Room Tags")
								t.Start()
								try:
									for target_ele in new_elements:
										if target_ele.Id not in [e.Id for e in selected_elements]:
											if not target_ele.IsValidObject:
												continue
											
											target_point = None
											try:
												if target_ele.Location:
													target_point = target_ele.Location.Point
												else:
													try:
														bbox = target_ele.get_BoundingBox(view)
														if bbox:
															target_point = (bbox.Min + bbox.Max) / 2
													except:
														continue
											except:
												continue
											
											vector_move = tinh_toan_phuong_align(reference_point, target_point)
											move_element(doc, target_ele, vector_move)
											selected_elements.append(target_ele)
								finally:
									t.Commit()
							else:
								break
						except Autodesk.Revit.Exceptions.OperationCanceledException:
							break
						except:
							continue
				
				return selected_elements
			except:
				return selected_elements
		
		def main():
			pick_room_tags()

		main()

	elif category in ["Tags", "Multi-Category Tags", "Wall Tags", "Structural Framing Tags", "Structural Foundation Tags", "Structural Column Tags", "Floor Tags", "Door Tags", "Window Tags", "Generic Model Tags", "Casework Tags", "Detail Item Tags"]:
		def tinh_toan_phuong_align(reference_point, target_point):
			try:
				if reference_point is None or target_point is None:
					return XYZ(0, 0, 0)
				
				vector = XYZ(reference_point.X - target_point.X, 
						   reference_point.Y - target_point.Y, 
						   reference_point.Z - target_point.Z)
				
				if view.ViewType in [DB.ViewType.FloorPlan, DB.ViewType.CeilingPlan, DB.ViewType.EngineeringPlan]:
					if abs(vector.Y) > abs(vector.X):
						new_point = XYZ(reference_point.X, target_point.Y, target_point.Z)
					else:
						new_point = XYZ(target_point.X, reference_point.Y, target_point.Z)
					move_vector = XYZ(new_point.X - target_point.X, 
									new_point.Y - target_point.Y, 
									new_point.Z - target_point.Z)
				elif view.ViewType == DB.ViewType.Section:
					right_dir = view.RightDirection
					# Check if section is parallel to Y-axis (RightDirection ≈ (0, ±1, 0))
					if abs(right_dir.Y) > 0.99 and abs(right_dir.X) < 0.01 and abs(right_dir.Z) < 0.01:
						y_diff = abs(reference_point.Y - target_point.Y)
						z_diff = abs(reference_point.Z - target_point.Z)
						if y_diff < z_diff:
							# Align along Y
							new_point = XYZ(target_point.X, reference_point.Y, target_point.Z)
						else:
							# Align along Z
							new_point = XYZ(target_point.X, target_point.Y, reference_point.Z)
					# Check if section is parallel to X-axis (RightDirection ≈ (±1, 0, 0))
					elif abs(right_dir.X) > 0.99 and abs(right_dir.Y) < 0.01 and abs(right_dir.Z) < 0.01:
						x_diff = abs(reference_point.X - target_point.X)
						z_diff = abs(reference_point.Z - target_point.Z)
						if x_diff < z_diff:
							# Align along X
							new_point = XYZ(reference_point.X, target_point.Y, target_point.Z)
						else:
							# Align along Z
							new_point = XYZ(target_point.X, target_point.Y, reference_point.Z)
					else:
						# Default to Z alignment for other section orientations
						new_point = XYZ(target_point.X, target_point.Y, reference_point.Z)
					move_vector = XYZ(new_point.X - target_point.X, 
									new_point.Y - target_point.Y, 
									new_point.Z - target_point.Z)
				else:
					move_vector = XYZ(0, 0, 0)
				return move_vector
			except:
				return XYZ(0, 0, 0)
		
		class FloorTagSelectionFilter(Autodesk.Revit.UI.Selection.ISelectionFilter):
			def AllowElement(self, element):
				return isinstance(element, IndependentTag) and element.Category.Name == "Floor Tags"
		
		class DoorTagSelectionFilter(Autodesk.Revit.UI.Selection.ISelectionFilter):
			def AllowElement(self, element):
				return isinstance(element, IndependentTag) and element.Category.Name == "Door Tags"
		
		class WindowTagSelectionFilter(Autodesk.Revit.UI.Selection.ISelectionFilter):
			def AllowElement(self, element):
				return isinstance(element, IndependentTag) and element.Category.Name == "Window Tags"
		
		class GenericModelTagSelectionFilter(Autodesk.Revit.UI.Selection.ISelectionFilter):
			def AllowElement(self, element):
				return isinstance(element, IndependentTag) and element.Category.Name == "Generic Model Tags"
		
		class CaseworkTagSelectionFilter(Autodesk.Revit.UI.Selection.ISelectionFilter):
			def AllowElement(self, element):
				return isinstance(element, IndependentTag) and element.Category.Name == "Casework Tags"
		
		class DetailItemTagSelectionFilter(Autodesk.Revit.UI.Selection.ISelectionFilter):
			def AllowElement(self, element):
				return isinstance(element, IndependentTag) and element.Category.Name == "Detail Item Tags"
		
		class StructuralFoundationTagSelectionFilter(Autodesk.Revit.UI.Selection.ISelectionFilter):
			def AllowElement(self, element):
				return isinstance(element, IndependentTag) and element.Category.Name == "Structural Foundation Tags"
		
		class StructuralColumnTagSelectionFilter(Autodesk.Revit.UI.Selection.ISelectionFilter):
			def AllowElement(self, element):
				return isinstance(element, IndependentTag) and element.Category.Name == "Structural Column Tags"
		
		class GenericTagSelectionFilter(Autodesk.Revit.UI.Selection.ISelectionFilter):
			def AllowElement(self, element):
				return isinstance(element, IndependentTag) and element.Category.Name in ["Tags", "Multi-Category Tags", "Wall Tags", "Structural Framing Tags"]
		
		def pick_tags():
			selected_elements = []
			try:
				reference_point = None
				try:
					reference_point = reference_ele.TagHeadPosition
				except:
					try:
						if reference_ele.Location:
							reference_point = reference_ele.Location.Point
					except:
						return selected_elements
				
				if reference_point is None:
					return selected_elements
				
				if category == "Floor Tags":
					selection_filter = FloorTagSelectionFilter()
					tag_type = "Floor Tag"
				elif category == "Door Tags":
					selection_filter = DoorTagSelectionFilter()
					tag_type = "Door Tag"
				elif category == "Window Tags":
					selection_filter = WindowTagSelectionFilter()
					tag_type = "Window Tag"
				elif category == "Generic Model Tags":
					selection_filter = GenericModelTagSelectionFilter()
					tag_type = "Generic Model Tag"
				elif category == "Casework Tags":
					selection_filter = CaseworkTagSelectionFilter()
					tag_type = "Casework Tag"
				elif category == "Detail Item Tags":
					selection_filter = DetailItemTagSelectionFilter()
					tag_type = "Detail Item Tag"
				elif category == "Structural Foundation Tags":
					selection_filter = StructuralFoundationTagSelectionFilter()
					tag_type = "Structural Foundation Tag"
				elif category == "Structural Column Tags":
					selection_filter = StructuralColumnTagSelectionFilter()
					tag_type = "Structural Column Tag"
				else:
					selection_filter = GenericTagSelectionFilter()
					tag_type = "Tag"
				
				first_prompt = "Click để chọn một " + tag_type + " để align (ESC để chuyển sang quét chuột)"
				subsequent_prompt = "Click để chọn thêm " + tag_type + " để align (ESC để chuyển sang quét chuột)"
				rectangle_first_prompt = "Quét chuột để chọn " + tag_type + "s (ESC để thoát)"
				rectangle_subsequent_prompt = "Quét chuột để chọn thêm " + tag_type + "s (ESC để thoát)"
				
				t = Transaction(doc, "Align " + tag_type + "s")
				t.Start()
				try:
					with forms.WarningBar(title=first_prompt):
						while True:
							try:
								prompt = first_prompt if not selected_elements else subsequent_prompt
								with forms.WarningBar(title=prompt):
									elem = uidoc.Selection.PickObject(
										ObjectType.Element,
										selection_filter,
										prompt
									)
								target_ele = doc.GetElement(elem.ElementId)
								if not target_ele.IsValidObject:
									continue
								
								target_point = None
								try:
									target_point = target_ele.TagHeadPosition
								except:
									try:
										if target_ele.Location:
											target_point = target_ele.Location.Point
										else:
											continue
									except:
										continue
								
								vector_move = tinh_toan_phuong_align(reference_point, target_point)
								move_element(doc, target_ele, vector_move)
								selected_elements.append(target_ele)
							except Autodesk.Revit.Exceptions.OperationCanceledException:
								break
							except:
								continue
				finally:
					t.Commit()
				
				if not selected_elements:
					while True:
						try:
							prompt = rectangle_first_prompt if not selected_elements else rectangle_subsequent_prompt
							with forms.WarningBar(title=prompt):
								new_elements = uidoc.Selection.PickElementsByRectangle(
									selection_filter,
									"Chọn " + tag_type + "s"
								)
							if new_elements:
								t = Transaction(doc, "Align " + tag_type + "s")
								t.Start()
								try:
									for target_ele in new_elements:
										if target_ele.Id not in [e.Id for e in selected_elements]:
											if not target_ele.IsValidObject:
												continue
											
											target_point = None
											try:
												target_point = target_ele.TagHeadPosition
											except:
												try:
													if target_ele.Location:
														target_point = target_ele.Location.Point
													else:
														continue
												except:
													continue
											
											vector_move = tinh_toan_phuong_align(reference_point, target_point)
											move_element(doc, target_ele, vector_move)
											selected_elements.append(target_ele)
								finally:
									t.Commit()
							else:
								break
						except Autodesk.Revit.Exceptions.OperationCanceledException:
							break
						except:
							continue
				
				return selected_elements
			except:
				return selected_elements
		
		def main():
			pick_tags()

		main()

	elif category == "Generic Annotations":
		def tinh_toan_phuong_align(point1, point2):
			try:
				if point1 is None or point2 is None:
					return XYZ(0, 0, 0)
				vector = XYZ(point1.X - point2.X, point1.Y - point2.Y, point1.Z - point2.Z)
				if view.ViewType in [DB.ViewType.FloorPlan, DB.ViewType.CeilingPlan, DB.ViewType.EngineeringPlan]:
					if abs(vector.Y) > abs(vector.X):
						new_point = XYZ(point1.X, point2.Y, point2.Z)
					else:
						new_point = XYZ(point2.X, point1.Y, point2.Z)
				elif view.ViewType == DB.ViewType.Section:
					z_diff = point1.Z - point2.Z
					new_point = XYZ(point2.X, point2.Y, point1.Z)
				else:
					return XYZ(0, 0, 0)
				return XYZ(new_point.X - point2.X, new_point.Y - point2.Y, new_point.Z - point2.Z)
			except:
				return XYZ(0, 0, 0)
		
		class GenericAnnotationSelectionFilter(Autodesk.Revit.UI.Selection.ISelectionFilter):
			def AllowElement(self, element):
				return isinstance(element, AnnotationSymbol)
		
		def pick_generic_annotations():
			selected_elements = []
			reference_position = None
			try:
				if reference_ele.Location:
					reference_position = reference_ele.Location.Point
			except:
				return selected_elements
			
			if reference_position is None:
				return selected_elements
			
			first_prompt = "Click để chọn một Generic Annotation để align (ESC để chuyển sang quét chuột)"
			subsequent_prompt = "Click để chọn thêm Generic Annotation để align (ESC để chuyển sang quét chuột)"
			rectangle_first_prompt = "Quét chuột để chọn Generic Annotations (ESC để thoát)"
			rectangle_subsequent_prompt = "Quét chuột để chọn thêm Generic Annotations (ESC để thoát)"
			
			t = Transaction(doc, "Align Generic Annotations")
			t.Start()
			try:
				with forms.WarningBar(title=first_prompt):
					while True:
						try:
							prompt = first_prompt if not selected_elements else subsequent_prompt
							with forms.WarningBar(title=prompt):
								elem = uidoc.Selection.PickObject(
									ObjectType.Element,
									GenericAnnotationSelectionFilter(),
									prompt
								)
							target_ele = doc.GetElement(elem.ElementId)
							if not target_ele.IsValidObject:
								continue
							
							target_position = None
							try:
								if target_ele.Location:
									target_position = target_ele.Location.Point
								else:
									continue
							except:
								continue
							
							move_vector = tinh_toan_phuong_align(reference_position, target_position)
							move_element(doc, target_ele, move_vector)
							selected_elements.append(target_ele)
						except Autodesk.Revit.Exceptions.OperationCanceledException:
							break
						except:
							continue
			finally:
				t.Commit()
			
			if not selected_elements:
				while True:
					try:
						prompt = rectangle_first_prompt if not selected_elements else rectangle_subsequent_prompt
						with forms.WarningBar(title=prompt):
							new_elements = uidoc.Selection.PickElementsByRectangle(
								GenericAnnotationSelectionFilter(),
								"Chọn Generic Annotations"
							)
						if new_elements:
							t = Transaction(doc, "Align Generic Annotations")
							t.Start()
							try:
								for target_ele in new_elements:
									if target_ele.Id not in [e.Id for e in selected_elements]:
										if not target_ele.IsValidObject:
											continue
										
										target_position = None
										try:
											if target_ele.Location:
												target_position = target_ele.Location.Point
											else:
												continue
										except:
											continue
										
										move_vector = tinh_toan_phuong_align(reference_position, target_position)
										move_element(doc, target_ele, move_vector)
										selected_elements.append(target_ele)
							finally:
								t.Commit()
						else:
							break
					except Autodesk.Revit.Exceptions.OperationCanceledException:
						break
					except:
						continue
			
			return selected_elements
		
		def main():
			pick_generic_annotations()

		main()

	elif category == "Dimensions":
		def tinh_toan_vector_move(line1, line2):
			start_point1 = line1.Origin
			end_point2 = line2.Origin
			move_vector = XYZ(start_point1.X - end_point2.X, 
							start_point1.Y - end_point2.Y, 
							start_point1.Z - end_point2.Z)
			return move_vector
		
		class DimensionSelectionFilter(Autodesk.Revit.UI.Selection.ISelectionFilter):
			def AllowElement(self, element):
				return isinstance(element, Dimension)
		
		def pick_dimensions():
			selected_elements = []
			reference_line = reference_ele.Curve
			first_prompt = "Click để chọn một Dimension để align (ESC để chuyển sang quét chuột)"
			subsequent_prompt = "Click để chọn thêm Dimension để align (ESC để chuyển sang quét chuột)"
			rectangle_first_prompt = "Quét chuột để chọn Dimensions (ESC để thoát)"
			rectangle_subsequent_prompt = "Quét chuột để chọn thêm Dimensions (ESC để thoát)"
			
			t = Transaction(doc, "Align Dimensions")
			t.Start()
			try:
				with forms.WarningBar(title=first_prompt):
					while True:
						try:
							prompt = first_prompt if not selected_elements else subsequent_prompt
							with forms.WarningBar(title=prompt):
								elem = uidoc.Selection.PickObject(
									ObjectType.Element,
									DimensionSelectionFilter(),
									prompt
								)
							target_ele = doc.GetElement(elem.ElementId)
							target_line = target_ele.Curve
							vector_move = tinh_toan_vector_move(reference_line, target_line)
							move_element(doc, target_ele, vector_move)
							selected_elements.append(target_ele)
						except Autodesk.Revit.Exceptions.OperationCanceledException:
							break
						except:
							continue
			finally:
				t.Commit()
			
			if not selected_elements:
				while True:
					try:
						prompt = rectangle_first_prompt if not selected_elements else rectangle_subsequent_prompt
						with forms.WarningBar(title=prompt):
							new_elements = uidoc.Selection.PickElementsByRectangle(
								DimensionSelectionFilter(),
								"Chọn Dimensions"
							)
						if new_elements:
							t = Transaction(doc, "Align Dimensions")
							t.Start()
							try:
								for target_ele in new_elements:
									if target_ele.Id not in [e.Id for e in selected_elements]:
										target_line = target_ele.Curve
										vector_move = tinh_toan_vector_move(reference_line, target_line)
										move_element(doc, target_ele, vector_move)
										selected_elements.append(target_ele)
							finally:
								t.Commit()
						else:
							break
					except Autodesk.Revit.Exceptions.OperationCanceledException:
						break
					except:
						continue
			
			return selected_elements
		
		def main():
			pick_dimensions()

		main()

	elif category == "Lines":
		def tinh_toan_vector_move(line1, line2):
			start_point1 = line1.GetEndPoint(0)
			start_point2 = line2.GetEndPoint(0)
			move_vector = XYZ(start_point1.X - start_point2.X, 
							start_point1.Y - start_point2.Y, 
							start_point1.Z - start_point2.Z)
			return move_vector
		
		class LineSelectionFilter(Autodesk.Revit.UI.Selection.ISelectionFilter):
			def AllowElement(self, element):
				return isinstance(element, ModelCurve) or isinstance(element, DetailCurve)
		
		def pick_lines():
			selected_elements = []
			reference_line = reference_ele.GeometryCurve
			first_prompt = "Click để chọn một Line để align (ESC để chuyển sang quét chuột)"
			subsequent_prompt = "Click để chọn thêm Line để align (ESC để chuyển sang quét chuột)"
			rectangle_first_prompt = "Quét chuột để chọn Lines (ESC để thoát)"
			rectangle_subsequent_prompt = "Quét chuột để chọn thêm Lines (ESC để thoát)"
			
			t = Transaction(doc, "Align Lines")
			t.Start()
			try:
				with forms.WarningBar(title=first_prompt):
					while True:
						try:
							prompt = first_prompt if not selected_elements else subsequent_prompt
							with forms.WarningBar(title=prompt):
								elem = uidoc.Selection.PickObject(
									ObjectType.Element,
									LineSelectionFilter(),
									prompt
								)
							target_ele = doc.GetElement(elem.ElementId)
							target_line = target_ele.GeometryCurve
							vector_move = tinh_toan_vector_move(reference_line, target_line)
							move_element(doc, target_ele, vector_move)
							selected_elements.append(target_ele)
						except Autodesk.Revit.Exceptions.OperationCanceledException:
							break
						except:
							continue
			finally:
				t.Commit()
			
			if not selected_elements:
				while True:
					try:
						prompt = rectangle_first_prompt if not selected_elements else rectangle_subsequent_prompt
						with forms.WarningBar(title=prompt):
							new_elements = uidoc.Selection.PickElementsByRectangle(
								LineSelectionFilter(),
								"Chọn Lines"
							)
						if new_elements:
							t = Transaction(doc, "Align Lines")
							t.Start()
							try:
								for target_ele in new_elements:
									if target_ele.Id not in [e.Id for e in selected_elements]:
										target_line = target_ele.GeometryCurve
										vector_move = tinh_toan_vector_move(reference_line, target_line)
										move_element(doc, target_ele, vector_move)
										selected_elements.append(target_ele)
							finally:
								t.Commit()
						else:
							break
					except Autodesk.Revit.Exceptions.OperationCanceledException:
						break
					except:
						continue
			
			return selected_elements
		
		def main():
			pick_lines()

		main()

	tg.Assimilate()

except Exception as e:
	if tg.HasStarted():
		tg.RollBack()
