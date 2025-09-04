var setVars = {

	"all": group_2022,
	"adipose": group_2022_adipose,
	"bone": group_2022_bone,
	"cells": group_2022_cells,
	"exosome": group_2022_evboost,
	"media": group_2022_media,
	"umbilical_cord": group_2022_umbilical_cord,
	"table_data": table2022_table,
	"filename": "2022_PubsCitingRoosterBio",
	"tabname": "2022"
};


console.log("setVars = ")
console.log(setVars)

var mapMakerNow = mapMaker(setVars);
var tableMakerNow = tableMaker(setVars);
