
var tableMaker = function functionTableMaker(setVars)

{

  console.log('setVars.table_data = ')
  console.log(setVars.table_data)

  var table = new Tabulator("#tableRoosterBio_table", {
      data:setVars.table_data,           //load row data from array
      layout:"fitColumns",      //fit columns to width of table
      responsiveLayout:"hide",  //hide columns that dont fit on the table
      tooltips:true,            //show tool tips on cells
      addRowPos:"top",          //when adding a new row, add it to the top of the table
      history:true,             //allow undo and redo actions on the table
      pagination:"local",       //paginate the data
      paginationSize:100,         //allow 7 rows per page of data
      paginationCounter:"rows", //display count of paginated rows in footer
      movableColumns:true,      //allow column order to be changed
      initialSort:[             //set the initial sort order of the data
          {column:"name", dir:"asc"},
      ],
      columns:[                 //define the table columns

          //{title:"Exosome", field:"g_exosome", width:10,  hozAlign:"center", formatter:"tickCross", sorter:"boolean", editor:true, bottomCalc:"sum", bottomCalcParams:{precision:0}},
          //{title:"Bone", field:"g_bone", width:10,  hozAlign:"center", formatter:"tickCross", sorter:"boolean", editor:true},
          //{title:"Adipose", field:"g_adipose", width:10,  hozAlign:"center", formatter:"tickCross", sorter:"boolean", editor:true},
          //{title:"Cells", field:"g_cells", width:10,  hozAlign:"center", formatter:"tickCross", sorter:"boolean", editor:true},
          //{title:"Media", field:"g_media", width:10,  hozAlign:"center", formatter:"tickCross", sorter:"boolean", editor:true},
          //{title:"Umbilical cord", field:"g_umbilical_cord", width:10,  hozAlign:"center", formatter:"tickCross", sorter:"boolean", editor:true},

          {title:"Published by", field:"journal", width:180, editor:"input"},
          {title:"Title", field:"title", width:80, editor:"input"},
          {title:"Affiliation, Lead Author", field:"lead_aff", width:80, editor:"input"},
          {title:"Author, Lead", field:"author_lead", width:100, editor:"input"},
          {title:"Author, Anchor", field:"author_anchor", width:100, editor:"input"},
          {title:"Publisher", field:"journal", width:100, editor:"input"},
          {title:"Funded by", field:"funder", width:100, editor:"input"},

          {title:"URL", field:"doi_url", width:10, formatter:"link", formatterParams:{
              target:"_blank",
          }},

          {title:"Cited by", field:"cites", width:20, editor:"input", bottomCalc:"sum", bottomCalcParams:{precision:0}},

          {title:"DOI", field:"doi", width:80, formatter:"link", formatterParams:{
            //labelField:"name",
            urlPrefix:"https://doi.org/",
            target:"_blank",
          }},


        //  {title:"Task Progress", field:"progress", hozAlign:"left", formatter:"progress", editor:true},
        //  {title:"Gender", field:"gender", width:95, editor:"select", editorParams:{values:["male", "female"]}},
        //  {title:"Rating", field:"rating", formatter:"star", hozAlign:"center", width:100, editor:true},
          //{title:"Color", field:"col", width:130, editor:"input"},
          //{title:"Date Of Birth", field:"dob", width:130, sorter:"date", hozAlign:"center"},
          //{title:"Driver", field:"car", width:90,  hozAlign:"center", formatter:"tickCross", sorter:"boolean", editor:true},
      ],
      });


      var filename = setVars.filename + ".xlsx"
      console.log("filename = ")
      console.log(filename)
      var tabname = setVars.tabname
      console.log("tabname = ")
      console.log(tabname)


      //trigger download of data.xlsx file
      document.getElementById("download-csv").addEventListener("click", function(){
          table.download("csv", filename );
      });

      document.getElementById("download-xlsx").addEventListener("click", function(){
          table.download("xlsx", filename , {sheetName: tabname});
      });


};
