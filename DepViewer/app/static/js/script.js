$( document ).ready(function(){
    var vis = d3.select("#graph")
                .append("svg");    

    var w = 900,
        h = 900,
        r = 10
    vis.attr("width", w)
       .attr("height", h);

    vis.text("Our Graph")
        .select("#graph")

    vis.selectAll("circle.nodes")
        .data(nodes)
        .enter()
        .append("svg:circle")
        .attr("cx", function(d) { return d.x; })
        .attr("cy", function(d) { return d.y; })
        .attr("r", r)
        .attr("fill", "rgb(4, 116, 116)")

    vis.selectAll(".text")
        .data(nodes)
        .enter()
        .append("svg:text")
        .attr("x", function(d) { return d.x + r*3 })
        .attr("y", function(d) { return d.y + r/2})
        .text(function(d) {return d.name} )

    vis.selectAll(".line")
   .data(links)
   .enter()
   .append("line")
   .attr("x1", function(d) { return d.source.x })
   .attr("y1", function(d) { return d.source.y + r + 2 })
   .attr("x2", function(d) { return d.target.x })
   .attr("y2", function(d) { return d.target.y - r - 2 })
   .style("stroke", "rgb(0, 157, 1)")
   .style("stroke-width", "6")


});
